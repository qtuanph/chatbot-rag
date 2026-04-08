from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from openpyxl import load_workbook

from app.services.ocr import get_ocr_service

@dataclass
class IngestedNode:
    heading: str
    full_text: str
    summary: str | None = None
    page_range: str | None = None
    level: int = 0
    order_index: int = 0
    parent_ref: str | None = None


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
    return _extract_plain_text_nodes(filename, content)


def _extract_pdf_nodes(content: bytes) -> list[IngestedNode]:
    doc = fitz.open(stream=content, filetype="pdf")
    nodes: list[IngestedNode] = [IngestedNode(heading="Document", full_text="", summary=None, level=0, order_index=0)]
    order_index = 1
    for index, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if not text:
            text = _ocr_pdf_page(page)
        if not text:
            continue

        sections = _split_into_sections(text)
        if len(sections) == 1:
            body = sections[0]
            nodes.append(
                IngestedNode(
                    heading=f"Page {index}",
                    full_text=body,
                    summary=body[:240],
                    page_range=str(index),
                    level=1,
                    order_index=order_index,
                    parent_ref="Document",
                )
            )
            order_index += 1
            continue

        page_heading = f"Page {index}"
        nodes.append(
            IngestedNode(
                heading=page_heading,
                full_text=text[:500],
                summary=text[:240],
                page_range=str(index),
                level=1,
                order_index=order_index,
                parent_ref="Document",
            )
        )
        order_index += 1
        for section_index, section in enumerate(sections, start=1):
            nodes.append(
                IngestedNode(
                    heading=f"Section {index}.{section_index}",
                    full_text=section,
                    summary=section[:240],
                    page_range=str(index),
                    level=2,
                    order_index=order_index,
                    parent_ref=page_heading,
                )
            )
            order_index += 1

    return nodes if len(nodes) > 1 else [IngestedNode(heading="PDF", full_text="", summary=None)]


def _ocr_pdf_page(page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    return get_ocr_service().image_to_text(pix.tobytes("png"))


def _ocr_image_node(filename: str, content: bytes) -> IngestedNode:
    text = get_ocr_service().image_to_text(content)
    return IngestedNode(heading=Path(filename).name, full_text=text, summary=text[:240] if text else None)


def _extract_docx_nodes(content: bytes) -> list[IngestedNode]:
    document = DocxDocument(BytesIO(content))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    if not paragraphs:
        return [IngestedNode(heading="DOCX", full_text="", summary=None)]
    return _make_chunk_nodes("Document", "\n".join(paragraphs), target_chars=1600)


def _extract_xlsx_nodes(content: bytes) -> list[IngestedNode]:
    workbook = load_workbook(BytesIO(content), data_only=True)
    nodes: list[IngestedNode] = [IngestedNode(heading="Document", full_text="", summary=None, level=0, order_index=0)]
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
                    heading=sheet.title,
                    full_text=text,
                    summary=text[:240],
                    level=1,
                    order_index=order_index,
                    parent_ref="Document",
                )
            )
            order_index += 1
    return nodes if len(nodes) > 1 else [IngestedNode(heading="XLSX", full_text="", summary=None)]


def _extract_plain_text_nodes(filename: str, content: bytes) -> list[IngestedNode]:
    text = content.decode("utf-8", errors="ignore").strip()
    if not text:
        return [IngestedNode(heading=Path(filename).name, full_text="", summary=None)]
    return _make_chunk_nodes(Path(filename).name, text, target_chars=1600)


def _split_into_sections(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    sections: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if _looks_like_heading(line) and buffer:
            sections.append("\n".join(buffer).strip())
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        sections.append("\n".join(buffer).strip())

    return [section for section in sections if section]


def _looks_like_heading(line: str) -> bool:
    if len(line) > 120:
        return False
    return line.isupper() or line.endswith(":") or line[:2].isdigit()


def _make_chunk_nodes(heading: str, text: str, target_chars: int) -> list[IngestedNode]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [IngestedNode(heading=heading, full_text="", summary=None)]

    nodes: list[IngestedNode] = [IngestedNode(heading=heading, full_text="", summary=None, level=0, order_index=0)]
    chunk: list[str] = []
    chunk_size = 0
    order_index = 1

    for line in lines:
        chunk.append(line)
        chunk_size += len(line) + 1
        if chunk_size >= target_chars:
            body = "\n".join(chunk)
            nodes.append(
                IngestedNode(
                    heading=f"{heading} {order_index}",
                    full_text=body,
                    summary=body[:240],
                    level=1,
                    order_index=order_index,
                    parent_ref=heading,
                )
            )
            order_index += 1
            chunk = []
            chunk_size = 0

    if chunk:
        body = "\n".join(chunk)
        nodes.append(
            IngestedNode(
                heading=f"{heading} {order_index}",
                full_text=body,
                summary=body[:240],
                level=1,
                order_index=order_index,
                parent_ref=heading,
            )
        )

    return nodes
