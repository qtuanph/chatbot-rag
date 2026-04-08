from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import fitz
from docx import Document as DocxDocument
from openpyxl import load_workbook

from app.services.ocr import get_ocr_service

@dataclass
class IngestedNode:
    ref: str
    heading: str
    full_text: str
    summary: str | None = None
    page_range: str | None = None
    level: int = 0
    order_index: int = 0
    parent_ref: str | None = "root"


def extract_nodes(filename: str, content: bytes) -> list[IngestedNode]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_nodes(content)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        return [_ocr_image_node(filename, content)]
    if suffix == ".docx":
        return _extract_docx_nodes(content)
    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return _extract_xlsx_nodes(content)
    if suffix == ".md":
        return _extract_markdown_nodes(content)
    return _extract_plain_text_nodes(filename, content)


def _extract_pdf_nodes(content: bytes) -> list[IngestedNode]:
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        nodes: list[IngestedNode] = []
        order_index = 1
        for index, page in enumerate(doc, start=1):
            text = _normalize_text(page.get_text("text"))
            if not text:
                text = _normalize_text(_ocr_pdf_page(page))
            if not text:
                continue

            sections = _split_into_sections(text)
            if len(sections) == 1:
                body = sections[0]
                nodes.append(
                    IngestedNode(
                        ref=f"page:{index}",
                        heading=f"Page {index}",
                        full_text=body,
                        summary=body[:240],
                        page_range=str(index),
                        level=1,
                        order_index=order_index,
                        parent_ref="root",
                    )
                )
                order_index += 1
                continue

            page_heading = f"Page {index}"
            nodes.append(
                IngestedNode(
                    ref=f"page:{index}",
                    heading=page_heading,
                    full_text=text,
                    summary=text[:240],
                    page_range=str(index),
                    level=1,
                    order_index=order_index,
                    parent_ref="root",
                )
            )
            order_index += 1
            for section_index, section in enumerate(sections, start=1):
                nodes.append(
                    IngestedNode(
                        ref=f"section:{index}:{section_index}",
                        heading=f"Section {index}.{section_index}",
                        full_text=section,
                        summary=section[:240],
                        page_range=str(index),
                        level=2,
                        order_index=order_index,
                        parent_ref=f"page:{index}",
                    )
                )
                order_index += 1

        toc_nodes = _extract_pdf_toc_nodes(doc, nodes, order_index)
        nodes.extend(toc_nodes)

        return nodes
    finally:
        doc.close()


def _extract_pdf_toc_nodes(doc, existing_nodes: list[IngestedNode], start_order: int) -> list[IngestedNode]:
    try:
        toc = doc.get_toc(simple=True)
    except Exception:
        return []

    if not toc:
        return []

    page_to_ref: dict[int, str] = {}
    for node in existing_nodes:
        if node.ref.startswith("page:"):
            try:
                page_no = int(node.ref.split(":", 1)[1])
                page_to_ref[page_no] = node.ref
            except Exception:
                continue

    level_last_ref: dict[int, str] = {}
    toc_nodes: list[IngestedNode] = []
    order_index = start_order
    for idx, item in enumerate(toc, start=1):
        if len(item) < 3:
            continue
        level, title, page = item[0], str(item[1]).strip(), int(item[2])
        if not title:
            continue
        parent_ref = "root"
        if level > 1 and (level - 1) in level_last_ref:
            parent_ref = level_last_ref[level - 1]
        elif page in page_to_ref:
            parent_ref = page_to_ref[page]

        ref = f"toc:{idx}"
        level_last_ref[level] = ref
        toc_nodes.append(
            IngestedNode(
                ref=ref,
                heading=title,
                full_text=title,
                summary=title,
                page_range=str(page),
                level=max(1, min(level + 1, 6)),
                order_index=order_index,
                parent_ref=parent_ref,
            )
        )
        order_index += 1

    return toc_nodes


def _ocr_pdf_page(page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    return get_ocr_service().image_to_text(pix.tobytes("png"))


def _ocr_image_node(filename: str, content: bytes) -> IngestedNode:
    text = _normalize_text(get_ocr_service().image_to_text(content))
    return IngestedNode(
        ref=f"image:{Path(filename).name}",
        heading=Path(filename).name,
        full_text=text,
        summary=text[:240] if text else None,
        level=1,
        parent_ref="root",
    )


def _extract_docx_nodes(content: bytes) -> list[IngestedNode]:
    document = DocxDocument(BytesIO(content))
    nodes: list[IngestedNode] = []
    order_index = 1
    current_heading = "Section"
    current_ref = "section:1"
    heading_count = 1
    buffer: list[str] = []

    def flush_chunk() -> None:
        nonlocal order_index
        if not buffer:
            return
        body = _normalize_text("\n".join(buffer))
        if not body:
            return
        nodes.append(
            IngestedNode(
                ref=f"docx:{order_index}",
                heading=current_heading,
                full_text=body,
                summary=body[:240],
                level=2,
                order_index=order_index,
                parent_ref=current_ref,
            )
        )
        order_index += 1

    for p in document.paragraphs:
        text = _normalize_text(p.text)
        if not text:
            continue
        style_name = (p.style.name or "").lower()
        if style_name.startswith("heading"):
            flush_chunk()
            heading_count += 1
            current_heading = text
            current_ref = f"docx-heading:{heading_count}"
            nodes.append(
                IngestedNode(
                    ref=current_ref,
                    heading=text,
                    full_text=text,
                    summary=text[:240],
                    level=1,
                    order_index=order_index,
                    parent_ref="root",
                )
            )
            order_index += 1
            buffer = []
            continue
        buffer.append(text)

    flush_chunk()
    if not nodes:
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        return _make_chunk_nodes("Document", "\n".join(paragraphs), target_chars=1600)
    return nodes


def _extract_xlsx_nodes(content: bytes) -> list[IngestedNode]:
    workbook = load_workbook(BytesIO(content), data_only=True)
    nodes: list[IngestedNode] = []
    order_index = 1
    for sheet in workbook.worksheets:
        rows: list[str] = []
        for row in sheet.iter_rows(values_only=True):
            values = ["" if cell is None else str(cell).strip() for cell in row]
            line = " | ".join(value for value in values if value)
            if line:
                rows.append(line)
        if rows:
            text = "\n".join(rows)
            nodes.append(
                IngestedNode(
                    ref=f"sheet:{order_index}",
                    heading=sheet.title,
                    full_text=text,
                    summary=text[:240],
                    level=1,
                    order_index=order_index,
                    parent_ref="root",
                )
            )
            order_index += 1
    return nodes


def _extract_markdown_nodes(content: bytes) -> list[IngestedNode]:
    text = _normalize_text(content.decode("utf-8", errors="ignore"))
    if not text:
        return []

    lines = text.splitlines()
    nodes: list[IngestedNode] = []
    order_index = 1
    section_buffer: list[str] = []
    section_heading = "Document"
    section_level = 1
    section_ref = "md:root"
    level_stack: dict[int, str] = {0: "root"}

    def flush_section() -> None:
        nonlocal order_index
        if not section_buffer:
            return
        body = _normalize_text("\n".join(section_buffer))
        if not body:
            return
        parent_level = max(section_level - 1, 0)
        parent_ref = level_stack.get(parent_level, "root")
        nodes.append(
            IngestedNode(
                ref=section_ref,
                heading=section_heading,
                full_text=body,
                summary=body[:240],
                level=max(1, section_level),
                order_index=order_index,
                parent_ref=parent_ref,
            )
        )
        order_index += 1

    section_counter = 1
    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if heading_match:
            flush_section()
            hashes, title = heading_match.groups()
            level = len(hashes)
            section_heading = title.strip()
            section_level = level
            section_ref = f"md:{section_counter}"
            section_counter += 1
            level_stack[level] = section_ref
            for deeper in range(level + 1, 8):
                level_stack.pop(deeper, None)
            section_buffer = [section_heading]
            continue
        section_buffer.append(line)

    flush_section()
    if not nodes:
        return _make_chunk_nodes("Document", text, target_chars=1600)
    return nodes


def _extract_plain_text_nodes(filename: str, content: bytes) -> list[IngestedNode]:
    text = _normalize_text(content.decode("utf-8", errors="ignore"))
    if not text:
        return []
    md_like = _extract_markdown_nodes(content)
    if md_like:
        return md_like
    return _make_chunk_nodes(Path(filename).name, text, target_chars=1600)


def _split_into_sections(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    sections: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if _looks_like_heading(line) and buffer and len(" ".join(buffer)) >= 120:
            sections.append("\n".join(buffer).strip())
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        sections.append("\n".join(buffer).strip())

    return [section for section in sections if section]


def _looks_like_heading(line: str) -> bool:
    if len(line) > 120 or len(line) < 3:
        return False
    if line.endswith(":"):
        return True
    if re.match(r"^(\d+(?:\.\d+){0,3})\s+\S+", line):
        return True
    alpha = [ch for ch in line if ch.isalpha()]
    if alpha:
        upper_ratio = sum(ch.isupper() for ch in alpha) / len(alpha)
        if upper_ratio >= 0.85 and len(line.split()) <= 12:
            return True
    return False


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _make_chunk_nodes(heading: str, text: str, target_chars: int) -> list[IngestedNode]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    nodes: list[IngestedNode] = []
    chunk: list[str] = []
    chunk_size = 0
    order_index = 1
    label_prefix = heading if heading != "Document" else "Section"

    for line in lines:
        chunk.append(line)
        chunk_size += len(line) + 1
        if chunk_size >= target_chars:
            body = "\n".join(chunk)
            nodes.append(
                IngestedNode(
                    ref=f"chunk:{order_index}",
                    heading=f"{label_prefix} {order_index}",
                    full_text=body,
                    summary=body[:240],
                    level=1,
                    order_index=order_index,
                    parent_ref="root",
                )
            )
            order_index += 1
            chunk = []
            chunk_size = 0

    if chunk:
        body = "\n".join(chunk)
        nodes.append(
            IngestedNode(
                ref=f"chunk:{order_index}",
                heading=f"{label_prefix} {order_index}",
                full_text=body,
                summary=body[:240],
                level=1,
                order_index=order_index,
                parent_ref="root",
            )
        )

    return nodes
