"""
Docling Parser: Primary document parser using Docling iterate_items() API.
OCR: PaddleOCR (RapidOCR ONNX) — mandatory, no fallback.
If OCR fails → document parsing fails with clear error.
"""

import logging
import uuid
import os
import tempfile
import re
import asyncio

from app.adapters.base import (
    BaseParser,
    IngestedNode,
    ParsingMetadata,
    ParsedNodeType,
)
from app.core.file_formats import extract_file_format
from app.core.exceptions import ParsingException

logger = logging.getLogger(__name__)


class DoclingParser(BaseParser):
    """
    Primary parser using Docling iterate_items() for 100% metadata preservation.
    OCR: PaddleOCR (RapidOCR ONNX backend) — MANDATORY for all documents.
    """

    def __init__(self, min_quality_score: float = 0.5):
        self.min_quality_score = min_quality_score
        self._initialize_docling()

    def _initialize_docling(self) -> None:
        """Initialize Docling converter with MANDATORY PaddleOCR."""
        from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption, WordFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions

        ocr_options = RapidOcrOptions(lang=["vi", "en"])
        pipeline = PdfPipelineOptions(
            do_ocr=True,
            force_full_page_ocr=True,
            ocr_options=ocr_options,
            do_table_structure=True,
        )

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline),
                InputFormat.DOCX: WordFormatOption(),
            }
        )
        logger.info("Docling+PaddleOCR initialized [vi, en]")

    async def parse(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
    ) -> tuple[list[IngestedNode], ParsingMetadata]:
        """Parse document with Docling + PaddleOCR."""
        import time

        start_time = time.time()
        source_format = extract_file_format(filename)

        result = await self._convert_with_docling(filename, content)
        if not result:
            raise ParsingException(f"Docling conversion failed for {filename}")

        # Primary extraction: direct from items
        nodes, sections_data, ok = self._extract_from_docling_items(
            result.document, document_id or filename, source_format
        )

        # Fallback within Docling: markdown export (if direct items fail)
        if not ok or not nodes:
            markdown_content = result.document.export_to_markdown()
            nodes, sections_data, ok = self._extract_sections_from_markdown(markdown_content, filename, source_format)

        if not ok or not nodes:
            raise ParsingException(f"Failed to extract content from {filename}")

        quality_score = self._calculate_quality_score(nodes, 0)
        metadata = ParsingMetadata(
            engine_used="docling+paddleocr",
            source_format=source_format,
            docling_used=True,
            fallback_used=False,
            quality_score=quality_score,
            parse_time_ms=(time.time() - start_time) * 1000,
            node_count=len(nodes),
            total_text_chars=sum(len(n.text) for n in nodes),
            sections_data=self._refine_sections(sections_data),
        )

        return self._refine_nodes(nodes), metadata

    # ── Docling conversion (single pass: always OCR) ────────────────────────

    async def _convert_with_docling(
        self,
        filename: str,
        content: bytes,
    ) -> object | None:
        """
        Convert document using Docling + PaddleOCR.
        Always runs OCR on every page (force_full_page_ocr=True).

        Returns: ConversionResult or None
        """
        if not self.converter:
            logger.error("Docling converter not initialized — PaddleOCR missing?")
            return None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(filename)[1],
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                logger.info("Converting %s with PaddleOCR...", filename)
                # DocumentConverter.convert does not accept a `timeout` kwarg (pydantic validation error).
                # Use asyncio.wait_for around the blocking call to enforce a timeout instead.
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(self.converter.convert, tmp_path), timeout=120
                    )
                except asyncio.TimeoutError:
                    logger.exception("Docling+PaddleOCR conversion TIMED OUT for %s", filename)
                    return None

                # Post-process: fix heading hierarchy via docling-hierarchical-pdf
                if filename.lower().endswith(".pdf"):
                    try:
                        from hierarchical.postprocessor import ResultPostprocessor

                        # source=tmp_path enables PDF-bookmark/ToC extraction via pymupdf.
                        # Without it, only stylistic inference (numbering, font size) runs.
                        ResultPostprocessor(result, source=tmp_path).process()
                        logger.info("Applied hierarchical heading post-processor")
                    except ImportError:
                        logger.debug("docling-hierarchical-pdf not installed, skipping hierarchy fix")
                    except Exception as e:
                        logger.warning("Hierarchical post-processor failed: %s", e)

                logger.info("Converted %s successfully", filename)
                return result
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            # Log full traceback to aid debugging (onnx/ocr native errors often hide stack details)
            logger.exception("Docling+PaddleOCR conversion FAILED for %s: %s", filename, e)
            return None

    # ── Method D: Extract directly from Docling items ────────────────────────

    def _get_page_number(self, item) -> int | None:
        """Extract page number from a Docling item's provenance."""
        prov = getattr(item, "prov", None)
        if not prov:
            return None
        for p in (prov if isinstance(prov, list) else [prov]):
            page_no = getattr(p, "page_no", None)
            if page_no is not None:
                return int(page_no)
            if isinstance(p, dict) and p.get("page_no") is not None:
                return int(p["page_no"])
        return None

    def _format_page_range(self, page_start: int | None, page_end: int | None) -> str | None:
        """Format a stable page span for display and ordering hints."""
        if page_start is None and page_end is None:
            return None
        if page_start is None:
            page_start = page_end
        if page_end is None:
            page_end = page_start
        if page_start == page_end:
            return str(page_start)
        return f"{page_start}-{page_end}"

    def _table_item_to_markdown(self, item) -> str:
        """Convert Docling TableItem to markdown table text."""
        data = getattr(item, "data", None)
        if not data or not data.table_cells:
            return ""
        num_cols = data.num_cols
        # Build row → col → cell text map
        rows: dict[int, dict[int, str]] = {}
        for cell in data.table_cells:
            row = cell.start_row_offset_idx
            col = cell.start_col_offset_idx
            if row not in rows:
                rows[row] = {}
            rows[row][col] = (getattr(cell, "text", "") or "").strip()

        lines = []
        for row_idx in sorted(rows.keys()):
            row_cells = rows[row_idx]
            values = [row_cells.get(c, "") for c in range(num_cols)]
            lines.append("| " + " | ".join(values) + " |")
            if row_idx == 0:  # Header separator after first row
                lines.append("| " + " | ".join(["---"] * num_cols) + " |")
        return "\n".join(lines)

    @staticmethod
    def _should_persist_section(section: dict) -> bool:
        """Persist section nodes even when they are content-light so hierarchy/page evidence is preserved."""
        return bool(
            section
            and (
                (section.get("content") or "").strip()
                or (section.get("title") or "").strip()
                or (section.get("image_count") or 0)
                or (section.get("table_count") or 0)
            )
        )

    @staticmethod
    def _is_noise_section(title: str, content: str, page_start: int | None) -> bool:
        """Filter empty sections from cover pages, TOC, and noise."""
        title = (title or "").strip()
        content = (content or "").strip()
        # Empty section on first 2 pages → likely cover noise
        if not content and len(title) < 40 and page_start and page_start <= 2:
            return True
        # Explicit TOC markers with no content
        if title.upper() in ("MỤC LỤC", "TABLE OF CONTENTS", "NỘI DUNG") and not content:
            return True
        return False

    @staticmethod
    def _correct_vietnamese_heading_level(title: str, current_level: int) -> int:
        """Override level for Vietnamese heading patterns that post-processor may miss."""
        t = (title or "").strip()
        # Top-level: Chương, Phần, Phụ lục
        if re.match(r"(?i)^(chương|phần|phụ lục)\s*[\dIVX]+", t):
            return 1
        # Second-level: Mục, Bài, Điều (standalone)
        if re.match(r"(?i)^(mục|bài|điều)\s*[\dIVX]+", t):
            return 2
        return current_level

    def _extract_from_docling_items(
        self,
        document,
        document_id: str,
        source_format: str,
    ) -> tuple[list[IngestedNode], list[dict], bool]:
        """
        Extract sections and chunks directly from Docling items.
        Preserves page numbers, heading levels, and table structures.

        Returns: (chunk_nodes, sections_data, success)
        """
        try:
            from app.core.config import settings

            chunk_size_tokens = settings.retrieval_chunk_size
            chunk_overlap_tokens = settings.retrieval_chunk_overlap

            # ── Phase 1: Build raw sections from iterate_items() ──────────
            sections_raw: list[dict] = []
            current_section: dict | None = None
            heading_stack: dict[int, str] = {}

            for item, _tree_level in document.iterate_items():
                item_label = getattr(item, "label", "") or ""
                item_text = getattr(item, "text", None) or ""
                page_no = self._get_page_number(item)

                # SectionHeaderItem → start new section
                if item_label == "section_header":
                    # Save previous section (skip noise)
                    if (
                        current_section
                        and not self._is_noise_section(
                            current_section.get("title", ""),
                            current_section.get("content", ""),
                            current_section.get("page_start"),
                        )
                        and self._should_persist_section(current_section)
                    ):
                        sections_raw.append(current_section)

                    level = getattr(item, "level", 1) or 1
                    title = item_text.strip()

                    # Vietnamese heading correction (supplement post-processor)
                    level = self._correct_vietnamese_heading_level(title, level)

                    # Update heading stack for breadcrumbs
                    heading_stack[level] = title
                    for heading_key in list(heading_stack.keys()):
                        if heading_key > level:
                            del heading_stack[heading_key]

                    breadcrumb = [heading_stack[heading_key] for heading_key in sorted(heading_stack.keys())]

                    # Find parent section
                    parent_section_id = None
                    if level > 1:
                        parent_level = level - 1
                        if parent_level in heading_stack:
                            for prev_sec in reversed(sections_raw):
                                if prev_sec["level"] == parent_level:
                                    parent_section_id = prev_sec["section_id"]
                                    break

                    current_section = {
                        "title": title,
                        "content": "",
                        "level": level,
                        "breadcrumb": breadcrumb,
                        "page_start": page_no,
                        "page_end": page_no,
                        "image_count": 0,
                        "table_count": 0,
                        "section_id": f"sec_{len(sections_raw):04d}",
                        "parent_section_id": parent_section_id,
                    }
                    continue

                # TitleItem → document title (treat as level 0 section)
                elif item_label == "title":
                    if (
                        current_section
                        and not self._is_noise_section(
                            current_section.get("title", ""),
                            current_section.get("content", ""),
                            current_section.get("page_start"),
                        )
                        and self._should_persist_section(current_section)
                    ):
                        sections_raw.append(current_section)
                    heading_stack = {}  # Reset for document title
                    heading_stack[0] = item_text.strip()
                    current_section = {
                        "title": item_text.strip(),
                        "content": "",
                        "level": 0,
                        "breadcrumb": [item_text.strip()],
                        "page_start": page_no,
                        "page_end": page_no,
                        "image_count": 0,
                        "table_count": 0,
                        "section_id": f"sec_{len(sections_raw):04d}",
                        "parent_section_id": None,
                    }
                    continue

                # TableItem → convert to markdown table
                elif item_label == "table":
                    if current_section is None:
                        current_section = {
                            "title": "Nội dung mở đầu",
                            "content": "",
                            "level": 1,
                            "breadcrumb": [],
                            "page_start": page_no,
                            "page_end": page_no,
                            "image_count": 0,
                            "table_count": 0,
                            "section_id": f"sec_{len(sections_raw):04d}",
                            "parent_section_id": None,
                        }
                    table_md = self._table_item_to_markdown(item)
                    if table_md:
                        current_section["content"] += table_md + "\n\n"
                        current_section["table_count"] += 1
                    if current_section is not None and page_no is not None:
                        current_section["page_end"] = page_no

                # TextItem / ListItem / CodeItem / FormulaItem → append text
                elif item_label in (
                    "paragraph",
                    "text",
                    "caption",
                    "footnote",
                    "reference",
                    "list_item",
                    "code",
                    "formula",
                    "marker",
                ):
                    if current_section is None:
                        current_section = {
                            "title": "Nội dung mở đầu",
                            "content": "",
                            "level": 1,
                            "breadcrumb": [],
                            "page_start": page_no,
                            "page_end": page_no,
                            "image_count": 0,
                            "table_count": 0,
                            "section_id": f"sec_{len(sections_raw):04d}",
                            "parent_section_id": None,
                        }
                    if item_text.strip():
                        prefix = "- " if item_label == "list_item" else ""
                        current_section["content"] += prefix + item_text.strip() + "\n\n"
                    if current_section is not None and page_no is not None:
                        current_section["page_end"] = page_no

                # PictureItem → skip (future: image caption extraction)
                elif item_label in ("picture",):
                    if current_section is not None:
                        current_section["image_count"] += 1
                        if page_no is not None:
                            current_section["page_end"] = page_no

            # Don't forget the last section (skip noise)
            if (
                current_section
                and not self._is_noise_section(
                    current_section.get("title", ""),
                    current_section.get("content", ""),
                    current_section.get("page_start"),
                )
                and self._should_persist_section(current_section)
            ):
                sections_raw.append(current_section)

            if not sections_raw:
                return [], [], False

            # ── Phase 2: Build sections_data + chunks ─────────────────────
            chunk_nodes: list[IngestedNode] = []
            sections_data: list[dict] = []
            global_order = 0

            for sec_idx, section in enumerate(sections_raw):
                section_id = section["section_id"]
                title = section["title"]
                content = section["content"]
                level = section["level"]
                breadcrumb = section["breadcrumb"]
                page_start = section.get("page_start")
                page_end = section.get("page_end")

                # Create section record for PostgreSQL
                sections_data.append(
                    {
                        "section_id": section_id,
                        "parent_section_id": section.get("parent_section_id"),
                        "title": title,
                        "content": content if content else None,
                        "section_type": "section",
                        "level": level,
                        "order_index": sec_idx,
                        "page_range": self._format_page_range(page_start, page_end),
                        "image_count": section.get("image_count", 0),
                        "table_count": section.get("table_count", 0),
                        "chunk_count": 0,
                        "breadcrumb": breadcrumb,
                        "metadata": {
                            "page_start": page_start,
                            "page_end": page_end,
                        },
                    }
                )

                # Split section content into chunks
                chunks = self._split_text_to_chunks(content, chunk_size_tokens, chunk_overlap_tokens)
                sections_data[-1]["chunk_count"] = len(chunks)

                # Create IngestedNode for each chunk
                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_nodes.append(
                        IngestedNode(
                            node_id=str(uuid.uuid4()),
                            document_id=document_id,
                            text=chunk_text,
                            node_type=ParsedNodeType.PARAGRAPH,
                            page_number=page_start,
                            section_title=title,
                            parent_id=None,
                            order=global_order,
                            metadata={
                                "source_format": source_format,
                                "section_id": section_id,
                                "section_level": level,
                                "chunk_index": chunk_idx,
                                "breadcrumb": breadcrumb,
                                "page_number": page_start,
                                "page_start": page_start,
                                "page_end": page_end,
                            },
                        )
                    )
                    global_order += 1

            logger.info(
                "Extracted %d sections → %d chunks (Method D) from %s",
                len(sections_data),
                len(chunk_nodes),
                document_id,
            )
            return chunk_nodes, sections_data, True

        except Exception as e:
            logger.warning("Method D extraction failed: %s", e)
            return [], [], False

    # ── Markdown fallback methods ────────────────────────────────────────────

    def _extract_sections_from_markdown(
        self,
        markdown_content: str,
        document_id: str,
        source_format: str,
    ) -> tuple[list[IngestedNode], list[dict], bool]:
        """
        Fallback: Split markdown into Sections → Chunks for 2-stage retrieval.
        Page numbers will be None (heuristic matching removed).
        """
        try:
            from app.core.config import settings

            chunk_size_tokens = settings.retrieval_chunk_size
            chunk_overlap_tokens = settings.retrieval_chunk_overlap

            sections_raw = self._split_markdown_by_headings(markdown_content)
            if not sections_raw:
                return [], [], False

            chunk_nodes: list[IngestedNode] = []
            sections_data: list[dict] = []
            global_order = 0

            for sec_idx, section in enumerate(sections_raw):
                section_id = f"sec_{sec_idx:04d}"
                title = section["title"]
                content = section["content"]
                level = section["level"]
                breadcrumb = section["breadcrumb"]

                sections_data.append(
                    {
                        "section_id": section_id,
                        "parent_section_id": section.get("parent_section_id"),
                        "title": title,
                        "content": content if content else None,
                        "section_type": "section",
                        "level": level,
                        "order_index": sec_idx,
                        "page_range": None,  # No page info in markdown path
                        "image_count": section.get("image_count", 0),
                        "table_count": section.get("table_count", 0),
                        "chunk_count": 0,
                        "breadcrumb": breadcrumb,
                        "metadata": {},
                    }
                )

                chunks = self._split_text_to_chunks(content, chunk_size_tokens, chunk_overlap_tokens)
                sections_data[-1]["chunk_count"] = len(chunks)

                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_nodes.append(
                        IngestedNode(
                            node_id=str(uuid.uuid4()),
                            document_id=document_id,
                            text=chunk_text,
                            node_type=ParsedNodeType.PARAGRAPH,
                            page_number=None,
                            section_title=title,
                            parent_id=None,
                            order=global_order,
                            metadata={
                                "source_format": source_format,
                                "section_id": section_id,
                                "section_level": level,
                                "chunk_index": chunk_idx,
                                "breadcrumb": breadcrumb,
                                "page_number": None,
                            },
                        )
                    )
                    global_order += 1

            logger.info(
                "Extracted %d sections → %d chunks (markdown fallback) from %s",
                len(sections_data),
                len(chunk_nodes),
                document_id,
            )
            return chunk_nodes, sections_data, True

        except Exception as e:
            logger.warning("Markdown section extraction failed: %s", e)
            return [], [], False

    # ── Shared utilities ─────────────────────────────────────────────────────

    def _split_markdown_by_headings(self, markdown: str) -> list[dict]:
        """Split markdown content into sections based on heading levels."""
        lines = markdown.split("\n")
        sections: list[dict] = []
        current_section: dict | None = None
        heading_stack: dict[int, str] = {}

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                if current_section and (
                    current_section["content"].strip()
                    or current_section["title"].strip()
                    or current_section.get("image_count", 0)
                    or current_section.get("table_count", 0)
                ):
                    sections.append(current_section)

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_stack[level] = title
                for heading_key in list(heading_stack.keys()):
                    if heading_key > level:
                        del heading_stack[heading_key]
                breadcrumb = [heading_stack[heading_key] for heading_key in sorted(heading_stack.keys())]

                current_section = {
                    "title": title,
                    "content": "",
                    "level": level,
                    "breadcrumb": breadcrumb,
                    "image_count": 0,
                    "table_count": 0,
                    "parent_section_id": None,
                }
                if level > 1:
                    parent_level = level - 1
                    if parent_level in heading_stack:
                        for prev_sec in reversed(sections):
                            if prev_sec["level"] == parent_level:
                                current_section["parent_section_id"] = f"sec_{sections.index(prev_sec):04d}"
                                break
            else:
                if current_section is None:
                    current_section = {
                        "title": "Nội dung mở đầu",
                        "content": "",
                        "level": 1,
                        "breadcrumb": [],
                        "image_count": 0,
                        "table_count": 0,
                        "parent_section_id": None,
                    }
                current_section["content"] += line + "\n"
                if self._TABLE_ROW.match(line.strip()):
                    current_section["table_count"] += 1

        if current_section and (
            current_section["content"].strip()
            or current_section["title"].strip()
            or current_section.get("image_count", 0)
            or current_section.get("table_count", 0)
        ):
            sections.append(current_section)
        return sections

    # Vietnamese abbreviations that should NOT trigger sentence breaks
    _VI_ABBREVIATIONS = re.compile(
        r"(?:Tp|TP|GS|PGS|TS|ThS|BS|DS|KS|KTS|ĐH|CĐ|TT|UBND|VNĐ|VN"
        r"|vol|Vol|No|no|tr|Tr|pg|Pg|ch|Ch|kt|Kt"
        r"|khoả|khoảng|độ|đồng|v.v"
        r")\.\s*$",
    )

    # Markdown table patterns
    _TABLE_ROW = re.compile(r"^\|.*\|$")
    _TABLE_SEPARATOR = re.compile(r"^\|[\s\-:|]+\|$")

    def _split_text_to_chunks(
        self,
        text: str,
        chunk_size: int = 400,
        overlap: int = 75,
    ) -> list[str]:
        """
        Recursive paragraph-first chunker optimized for Vietnamese documents.

        Strategy (aligned with 2026 RAG benchmark recommendations):
        1. Split into paragraphs (double newline boundaries)
        2. Within each paragraph, split into sentences (Vietnamese-aware)
        3. Accumulate sentences into chunks up to chunk_size tokens
        4. Overlap with complete sentences from previous chunk
        5. Never split markdown tables or list blocks mid-structure
        """
        if not text or not text.strip():
            return []

        chars_per_chunk = chunk_size * 3  # Vietnamese: ~3 chars/token (compound words, syllable spaces)
        overlap_chars = overlap * 3

        # Step 1: Split into paragraphs, preserving table/list blocks intact
        blocks = self._split_into_blocks(text)

        # Step 2: Within each block, split into sentences
        units: list[str] = []
        for block in blocks:
            if self._is_atomic_block(block):
                # Tables and lists stay as one unit regardless of size
                units.append(block)
            else:
                sentences = self._split_sentences(block)
                units.extend(sentences)

        units = [u.strip() for u in units if u.strip()]
        if not units:
            return [text.strip()] if text.strip() else []

        # Step 3: Accumulate into chunks with overlap
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for unit in units:
            unit_len = len(unit)
            if current_length + unit_len > chars_per_chunk and current_chunk:
                chunks.append("\n".join(current_chunk))
                # Overlap: take complete sentences from the tail
                overlap_units: list[str] = []
                overlap_len = 0
                for u in reversed(current_chunk):
                    if overlap_len + len(u) > overlap_chars:
                        break
                    overlap_units.insert(0, u)
                    overlap_len += len(u)
                current_chunk = overlap_units
                current_length = overlap_len
            current_chunk.append(unit)
            current_length += unit_len

        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)
        return chunks

    def _split_into_blocks(self, text: str) -> list[str]:
        """Split text into blocks: paragraphs, tables, and list groups.

        Table detection requires structural evidence (separator line or 3+ consecutive
        | lines) to avoid false positives on single | in math/technical text.
        """
        lines = text.split("\n")
        blocks: list[str] = []
        current_block: list[str] = []
        consecutive_table_lines = 0

        def _flush_block():
            nonlocal consecutive_table_lines
            if current_block:
                blocks.append("\n".join(current_block))
                current_block.clear()
            consecutive_table_lines = 0

        for line in lines:
            stripped = line.strip()
            is_table_row = bool(self._TABLE_ROW.match(stripped))
            is_table_sep = bool(self._TABLE_SEPARATOR.match(stripped))
            is_list = stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", stripped)

            if is_table_sep:
                if not current_block:
                    current_block = []
                current_block.append(line)
                consecutive_table_lines = max(consecutive_table_lines, 3)
            elif is_table_row and consecutive_table_lines >= 2:
                current_block.append(line)
                consecutive_table_lines += 1
            elif is_list:
                _flush_block()
                current_block.append(line)
            elif current_block and (
                current_block[-1].strip().startswith(("- ", "* ", "+ "))
                or re.match(r"^\d+\.\s", current_block[-1].strip())
            ):
                current_block.append(line)
            elif stripped == "":
                _flush_block()
            else:
                if consecutive_table_lines > 0 and consecutive_table_lines < 3:
                    consecutive_table_lines = 0
                current_block.append(line)

        if current_block:
            blocks.append("\n".join(current_block))
        return blocks

    def _is_atomic_block(self, block: str) -> bool:
        """Check if a block should not be further split (table or list group)."""
        lines = block.strip().split("\n")
        if not lines:
            return False
        # Multi-line table or list group
        if len(lines) > 1:
            table_lines = sum(1 for line_item in lines if self._TABLE_ROW.match(line_item.strip()))
            if table_lines >= 2:
                return True
            list_lines = sum(
                1
                for line_item in lines
                if line_item.strip().startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", line_item.strip())
            )
            if list_lines >= 2:
                return True
        return False

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences with Vietnamese-aware boundary detection."""
        # Split on sentence-ending punctuation followed by space/newline
        parts = re.split(r"(?<=[.!?。！？])\s+", text)
        sentences: list[str] = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Rejoin if the period was an abbreviation, not a sentence end
            if sentences and self._VI_ABBREVIATIONS.search(sentences[-1]):
                sentences[-1] = sentences[-1] + " " + part
            else:
                sentences.append(part)
        return sentences

    def _refine_nodes(self, nodes: list[IngestedNode]) -> list[IngestedNode]:
        """Simple text refinement: normalize whitespace and basic cleaning."""
        for node in nodes:
            # Fix common OCR artifacts and normalize spaces
            text = node.text or ""
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
            node.text = text.strip()
        return nodes

    def _refine_sections(self, sections_data: list[dict]) -> list[dict]:
        """Normalize section titles and content."""
        for sec in sections_data:
            for field in ["title", "content"]:
                if val := sec.get(field):
                    sec[field] = re.sub(r"\s+", " ", val).strip()
            if bread := sec.get("breadcrumb"):
                sec["breadcrumb"] = [re.sub(r"\s+", " ", b).strip() if b else b for b in bread]
        return sections_data

    def _infer_node_type(self, node) -> ParsedNodeType:
        """Infer node type from node text content."""
        text = getattr(node, "text", "") or ""
        metadata = getattr(node, "metadata", {}) or {}

        if metadata.get("node_type"):
            try:
                return ParsedNodeType(str(metadata["node_type"]).lower())
            except ValueError:
                pass

        if "```" in text or "def " in text or "class " in text:
            return ParsedNodeType.CODE_BLOCK
        elif "|" in text and text.count("\n") < 20:
            return ParsedNodeType.TABLE
        elif text.startswith("#") or text.startswith("##"):
            return ParsedNodeType.SECTION
        else:
            return ParsedNodeType.PARAGRAPH

    def _calculate_quality_score(self, nodes: list[IngestedNode], markdown_chars: int) -> float:
        """Calculate parse quality score (0-1)."""
        if not nodes:
            return 0.0

        avg_node_length = sum(len(n.text) for n in nodes) / len(nodes)
        length_score = min(avg_node_length / 500, 1.0)

        node_types = set(n.node_type for n in nodes)
        type_diversity = len(node_types) / len(ParsedNodeType)

        hierarchical_nodes = sum(1 for n in nodes if n.parent_id)
        hierarchy_score = min(hierarchical_nodes / len(nodes), 1.0)

        return min(
            max(
                length_score * 0.5 + type_diversity * 0.25 + hierarchy_score * 0.25,
                0.0,
            ),
            1.0,
        )
