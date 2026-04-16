"""
Docling Parser: Primary document parser using Docling iterate_items() API.
Extracts sections, chunks, page numbers, heading levels, and table structures
directly from Docling's native document model — no markdown export needed.
Falls back to markdown path if iterate_items() fails.
"""

import logging
import uuid
from typing import List, Tuple, Optional
import os
import tempfile
import re

from app.adapters.base import (
    BaseParser,
    IngestedNode,
    ParsingMetadata,
    ParsedNodeType,
)
from app.core.exceptions import ParsingException
from app.core.hardware import hardware

logger = logging.getLogger(__name__)

# Minimum chars per page to consider PDF as having embedded text (not scanned)
_MIN_CHARS_PER_PAGE = 50


class DoclingParser(BaseParser):
    """
    Primary parser using Docling iterate_items() for 100% metadata preservation.
    Falls back to markdown path on failure.
    """

    def __init__(
        self,
        fallback_parser: Optional['BaseParser'] = None,
        min_quality_score: float = 0.5,
    ):
        self.fallback_parser = fallback_parser
        self.min_quality_score = min_quality_score
        self.converter_fast = None   # do_ocr=False for native PDF text
        self.converter_ocr = None    # do_ocr=True for scanned PDF fallback
        self.llamaindex_parser = None

        self._initialize_docling()
        self._initialize_llamaindex()

    def _select_ocr_backend(self):
        """Build EasyOCR options for Vietnamese + English documents."""
        from docling.datamodel.pipeline_options import EasyOcrOptions
        use_gpu = hardware.gpu_count > 0
        opts = EasyOcrOptions(lang=["vi", "en"], use_gpu=use_gpu)
        logger.info("OCR backend: EasyOCR [vi, en] gpu=%s", use_gpu)
        return opts

    def _initialize_docling(self) -> None:
        """Initialize 2 Docling converters: fast (no OCR) + OCR fallback."""
        try:
            from docling.document_converter import (
                DocumentConverter,
                PdfFormatOption,
                ImageFormatOption,
            )
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            ocr_options = self._select_ocr_backend()

            # Fast converter: extract embedded text only, no OCR
            pipeline_fast = PdfPipelineOptions(
                do_ocr=False,
                do_table_structure=True,
            )

            # OCR converter: for scanned PDFs that have no embedded text
            pipeline_ocr = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options,
                do_table_structure=True,
            )

            # Image converter: always OCR
            pipeline_image = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options,
                do_table_structure=True,
            )

            image_fmt = ImageFormatOption(pipeline_options=pipeline_image)

            self.converter_fast = DocumentConverter(format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_fast),
                InputFormat.IMAGE: image_fmt,
            })

            self.converter_ocr = DocumentConverter(format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_ocr),
                InputFormat.IMAGE: image_fmt,
            })

            logger.info("Docling converters initialized: fast + OCR fallback")
        except ImportError:
            logger.warning("Docling not installed; will skip Docling parsing")
        except Exception as e:
            logger.warning("Failed to initialize Docling: %s", e)
            try:
                from docling.document_converter import DocumentConverter
                converter = DocumentConverter()
                self.converter_fast = converter
                self.converter_ocr = converter
                logger.info("Docling initialized with default settings")
            except Exception:
                logger.warning("Failed to initialize default Docling converter")

    def _initialize_llamaindex(self) -> None:
        """Lazy-initialize LlamaIndex Markdown parser."""
        try:
            from llama_index.core.node_parser import MarkdownNodeParser
            self.llamaindex_parser = MarkdownNodeParser()
            logger.info("LlamaIndex MarkdownNodeParser initialized")
        except ImportError:
            logger.warning("LlamaIndex not installed; skipping hierarchical parsing")
        except Exception as e:
            logger.warning("Failed to initialize LlamaIndex: %s", e)

    def parse(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[List[IngestedNode], ParsingMetadata]:
        """Parse document: Method D (iterate_items) → fallback markdown → fallback parser."""
        import time
        start_time = time.time()

        source_format = self._extract_format(filename)

        try:
            # Step 1: Convert with Docling
            result, docling_used = self._convert_with_docling(filename, content)

            if result:
                # Step 2a: Try Method D — extract directly from Docling items
                nodes, sections_data, ok = self._extract_from_docling_items(
                    result.document, filename, source_format,
                )

                if ok and nodes:
                    quality_score = self._calculate_quality_score(nodes, 0)
                    parse_time_ms = (time.time() - start_time) * 1000

                    metadata = ParsingMetadata(
                        engine_used="docling+items",
                        source_format=source_format,
                        docling_used=True,
                        llamaindex_used=False,
                        fallback_used=False,
                        quality_score=quality_score,
                        parse_time_ms=parse_time_ms,
                        node_count=len(nodes),
                        total_text_chars=sum(len(n.text) for n in nodes),
                        warnings=[],
                    )

                    nodes = self._refine_nodes(nodes)
                    metadata.sections_data = sections_data

                    logger.info(
                        "Parsed %s with Docling+Items: %d nodes, %d sections",
                        filename, len(nodes), len(sections_data),
                    )
                    return nodes, metadata

                # Step 2b: Fallback to markdown path
                markdown_content = result.document.export_to_markdown()
                if markdown_content:
                    nodes, sections_data, ok = self._extract_sections_from_markdown(
                        markdown_content, filename, source_format,
                    )
                    if ok and nodes:
                        quality_score = self._calculate_quality_score(nodes, len(markdown_content))
                        parse_time_ms = (time.time() - start_time) * 1000
                        metadata = ParsingMetadata(
                            engine_used="docling+sections",
                            source_format=source_format,
                            docling_used=True,
                            llamaindex_used=False,
                            fallback_used=False,
                            quality_score=quality_score,
                            parse_time_ms=parse_time_ms,
                            node_count=len(nodes),
                            total_text_chars=sum(len(n.text) for n in nodes),
                            warnings=[],
                        )
                        nodes = self._refine_nodes(nodes)
                        metadata.sections_data = sections_data
                        logger.info(
                            "Parsed %s with Docling+Sections(fallback): %d nodes",
                            filename, len(nodes),
                        )
                        return nodes, metadata

                    # Step 2c: LlamaIndex fallback
                    nodes, llamaindex_used = self._parse_markdown_with_llamaindex(
                        markdown_content, filename, source_format,
                    )
                    if nodes:
                        quality_score = self._calculate_quality_score(nodes, len(markdown_content))
                        parse_time_ms = (time.time() - start_time) * 1000
                        metadata = ParsingMetadata(
                            engine_used="docling+llamaindex",
                            source_format=source_format,
                            docling_used=True,
                            llamaindex_used=llamaindex_used,
                            fallback_used=False,
                            quality_score=quality_score,
                            parse_time_ms=parse_time_ms,
                            node_count=len(nodes),
                            total_text_chars=sum(len(n.text) for n in nodes),
                            warnings=[],
                        )
                        nodes = self._refine_nodes(nodes)
                        return nodes, metadata

        except Exception as e:
            logger.warning("Docling parsing failed for %s: %s", filename, e)

        # Step 3: Fallback parser
        if self.fallback_parser:
            try:
                nodes, fallback_metadata = self.fallback_parser.parse(filename, content)
                if nodes:
                    fallback_metadata.fallback_used = True
                    fallback_metadata.parse_time_ms = (time.time() - start_time) * 1000
                    logger.info("Parsed %s with fallback parser: %d nodes", filename, len(nodes))
                    return nodes, fallback_metadata
            except Exception as e:
                logger.warning("Fallback parser failed for %s: %s", filename, e)

        raise ParsingException(
            f"Failed to parse {filename}: all strategies failed",
            error_code="PARSING_ALL_STRATEGIES_FAILED",
            details={'filename': filename, 'source_format': source_format}
        )

    # ── Docling conversion (2-pass: fast → OCR if scanned) ──────────────────

    def _convert_with_docling(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[Optional[object], bool]:
        """
        Convert document using Docling with smart OCR strategy.

        Pass 1: Fast extraction (no OCR) — works for native PDF/DOCX.
        Pass 2: OCR fallback — only if Pass 1 yields very little text (scanned PDF).

        Returns: (ConversionResult or None, docling_used bool)
        """
        converter = self.converter_fast
        if not converter:
            return None, False

        try:
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(filename)[1],
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Pass 1: Fast (no OCR)
                result = converter.convert(tmp_path)

                # Check if this is a scanned PDF (very little text extracted)
                if self._is_scanned(result):
                    logger.info(
                        "%s appears scanned (low text density), re-processing with OCR",
                        filename,
                    )
                    if self.converter_ocr and self.converter_ocr is not converter:
                        result = self.converter_ocr.convert(tmp_path)
                        logger.info("Re-converted %s with OCR", filename)

                return result, True
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.warning("Docling conversion failed for %s: %s", filename, e)
            return None, False

    def _is_scanned(self, result) -> bool:
        """Detect if conversion result is a scanned document (very little text)."""
        try:
            total_chars = 0
            num_pages = 0
            for item, _level in result.document.iterate_items():
                text = getattr(item, 'text', None) or ''
                if text.strip():
                    total_chars += len(text.strip())
                # Count pages from provenance
                prov = getattr(item, 'prov', None)
                if prov:
                    for p in (prov if isinstance(prov, list) else [prov]):
                        page_no = getattr(p, 'page_no', None) or (p.get('page_no') if isinstance(p, dict) else None)
                        if page_no is not None:
                            num_pages = max(num_pages, page_no)

            if num_pages == 0:
                return total_chars < 100  # Very short document

            chars_per_page = total_chars / num_pages
            is_scanned = chars_per_page < _MIN_CHARS_PER_PAGE

            if is_scanned:
                logger.info(
                    "Scanned detection: %d chars / %d pages = %.0f chars/page (< %d threshold)",
                    total_chars, num_pages, chars_per_page, _MIN_CHARS_PER_PAGE,
                )

            return is_scanned
        except Exception:
            return False

    # ── Method D: Extract directly from Docling items ────────────────────────

    def _get_page_number(self, item) -> Optional[int]:
        """Extract page number from a Docling item's provenance."""
        prov = getattr(item, 'prov', None)
        if not prov:
            return None
        for p in (prov if isinstance(prov, list) else [prov]):
            page_no = getattr(p, 'page_no', None)
            if page_no is not None:
                return int(page_no)
            if isinstance(p, dict) and p.get('page_no') is not None:
                return int(p['page_no'])
        return None

    def _table_item_to_markdown(self, item) -> str:
        """Convert Docling TableItem to markdown table text."""
        data = getattr(item, 'data', None)
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
            rows[row][col] = (getattr(cell, 'text', '') or '').strip()

        lines = []
        for row_idx in sorted(rows.keys()):
            row_cells = rows[row_idx]
            values = [row_cells.get(c, "") for c in range(num_cols)]
            lines.append("| " + " | ".join(values) + " |")
            if row_idx == 0:  # Header separator after first row
                lines.append("| " + " | ".join(["---"] * num_cols) + " |")
        return "\n".join(lines)

    def _extract_from_docling_items(
        self,
        document,
        document_id: str,
        source_format: str,
    ) -> Tuple[List[IngestedNode], List[dict], bool]:
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
            sections_raw: List[dict] = []
            current_section: dict | None = None
            heading_stack: dict[int, str] = {}

            for item, _tree_level in document.iterate_items():
                item_label = getattr(item, 'label', '') or ''
                item_text = getattr(item, 'text', None) or ''
                page_no = self._get_page_number(item)

                # SectionHeaderItem → start new section
                if item_label == 'section_header':
                    # Save previous section
                    if current_section and current_section["content"].strip():
                        sections_raw.append(current_section)

                    level = getattr(item, 'level', 1) or 1
                    title = item_text.strip()

                    # Update heading stack for breadcrumbs
                    heading_stack[level] = title
                    for l in list(heading_stack.keys()):
                        if l > level:
                            del heading_stack[l]

                    breadcrumb = [heading_stack[l] for l in sorted(heading_stack.keys())]

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
                        "page_number": page_no,
                        "image_count": 0,
                        "table_count": 0,
                        "section_id": f"sec_{len(sections_raw):04d}",
                        "parent_section_id": parent_section_id,
                    }

                # TitleItem → document title (treat as level 0 section)
                elif item_label == 'title':
                    if current_section and current_section["content"].strip():
                        sections_raw.append(current_section)
                    heading_stack = {}  # Reset for document title
                    heading_stack[0] = item_text.strip()
                    current_section = {
                        "title": item_text.strip(),
                        "content": "",
                        "level": 0,
                        "breadcrumb": [item_text.strip()],
                        "page_number": page_no,
                        "image_count": 0,
                        "table_count": 0,
                        "section_id": f"sec_{len(sections_raw):04d}",
                        "parent_section_id": None,
                    }

                # TableItem → convert to markdown table
                elif item_label == 'table':
                    if current_section is None:
                        current_section = {
                            "title": "Nội dung mở đầu",
                            "content": "",
                            "level": 1,
                            "breadcrumb": [],
                            "page_number": page_no,
                            "image_count": 0,
                            "table_count": 0,
                            "section_id": f"sec_{len(sections_raw):04d}",
                            "parent_section_id": None,
                        }
                    table_md = self._table_item_to_markdown(item)
                    if table_md:
                        current_section["content"] += table_md + "\n\n"
                        current_section["table_count"] += 1

                # TextItem / ListItem / CodeItem / FormulaItem → append text
                elif item_label in ('paragraph', 'text', 'caption', 'footnote',
                                    'page_header', 'page_footer', 'reference',
                                    'list_item', 'code', 'formula', 'marker'):
                    if current_section is None:
                        current_section = {
                            "title": "Nội dung mở đầu",
                            "content": "",
                            "level": 1,
                            "breadcrumb": [],
                            "page_number": page_no,
                            "image_count": 0,
                            "table_count": 0,
                            "section_id": f"sec_{len(sections_raw):04d}",
                            "parent_section_id": None,
                        }
                    if item_text.strip():
                        prefix = "- " if item_label == 'list_item' else ""
                        current_section["content"] += prefix + item_text.strip() + "\n\n"

                # PictureItem → skip (future: image caption extraction)
                elif item_label in ('picture',):
                    if current_section is not None:
                        current_section["image_count"] += 1

            # Don't forget the last section
            if current_section and current_section["content"].strip():
                sections_raw.append(current_section)

            if not sections_raw:
                return [], [], False

            # ── Phase 2: Build sections_data + chunks ─────────────────────
            chunk_nodes: List[IngestedNode] = []
            sections_data: List[dict] = []
            global_order = 0

            for sec_idx, section in enumerate(sections_raw):
                section_id = section["section_id"]
                title = section["title"]
                content = section["content"]
                level = section["level"]
                breadcrumb = section["breadcrumb"]
                page_number = section["page_number"]

                # Create section record for PostgreSQL
                sections_data.append({
                    "section_id": section_id,
                    "parent_section_id": section.get("parent_section_id"),
                    "title": title,
                    "content": content[:5000] if content else None,
                    "section_type": "section",
                    "level": level,
                    "order_index": sec_idx,
                    "page_range": str(page_number) if page_number is not None else None,
                    "image_count": section.get("image_count", 0),
                    "table_count": section.get("table_count", 0),
                    "chunk_count": 0,
                    "breadcrumb": breadcrumb,
                    "metadata": {},
                })

                # Split section content into chunks
                chunks = self._split_text_to_chunks(
                    content, chunk_size_tokens, chunk_overlap_tokens
                )
                sections_data[-1]["chunk_count"] = len(chunks)

                # Create IngestedNode for each chunk
                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_nodes.append(IngestedNode(
                        node_id=str(uuid.uuid4()),
                        document_id=document_id,
                        text=chunk_text,
                        node_type=ParsedNodeType.PARAGRAPH,
                        page_number=page_number,
                        section_title=title,
                        parent_id=None,
                        order=global_order,
                        metadata={
                            "source_format": source_format,
                            "section_id": section_id,
                            "section_level": level,
                            "chunk_index": chunk_idx,
                            "breadcrumb": breadcrumb,
                            "page_number": page_number,
                        },
                    ))
                    global_order += 1

            logger.info(
                "Extracted %d sections → %d chunks (Method D) from %s",
                len(sections_data), len(chunk_nodes), document_id,
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
    ) -> Tuple[List[IngestedNode], List[dict], bool]:
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

            chunk_nodes: List[IngestedNode] = []
            sections_data: List[dict] = []
            global_order = 0

            for sec_idx, section in enumerate(sections_raw):
                section_id = f"sec_{sec_idx:04d}"
                title = section["title"]
                content = section["content"]
                level = section["level"]
                breadcrumb = section["breadcrumb"]

                sections_data.append({
                    "section_id": section_id,
                    "parent_section_id": section.get("parent_section_id"),
                    "title": title,
                    "content": content[:5000] if content else None,
                    "section_type": "section",
                    "level": level,
                    "order_index": sec_idx,
                    "page_range": None,  # No page info in markdown path
                    "image_count": section.get("image_count", 0),
                    "table_count": section.get("table_count", 0),
                    "chunk_count": 0,
                    "breadcrumb": breadcrumb,
                    "metadata": {},
                })

                chunks = self._split_text_to_chunks(
                    content, chunk_size_tokens, chunk_overlap_tokens
                )
                sections_data[-1]["chunk_count"] = len(chunks)

                for chunk_idx, chunk_text in enumerate(chunks):
                    chunk_nodes.append(IngestedNode(
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
                    ))
                    global_order += 1

            logger.info(
                "Extracted %d sections → %d chunks (markdown fallback) from %s",
                len(sections_data), len(chunk_nodes), document_id,
            )
            return chunk_nodes, sections_data, True

        except Exception as e:
            logger.warning("Markdown section extraction failed: %s", e)
            return [], [], False

    def _parse_markdown_with_llamaindex(
        self,
        markdown_content: str,
        document_id: str,
        source_format: str,
    ) -> Tuple[List[IngestedNode], bool]:
        """Parse Markdown content into hierarchical nodes using LlamaIndex."""
        if not self.llamaindex_parser:
            return [], False

        try:
            from llama_index.core.schema import Document
            doc = Document(text=markdown_content, metadata={'file_name': document_id})
            llamaindex_nodes = self.llamaindex_parser.get_nodes_from_documents([doc])

            nodes = []
            for idx, node in enumerate(llamaindex_nodes):
                parent_id = None
                if hasattr(node, 'relationships') and 'parent' in node.relationships:
                    parent_id = node.relationships['parent'].node_id

                nodes.append(IngestedNode(
                    node_id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=node.get_content(),
                    node_type=self._infer_node_type(node),
                    page_number=node.metadata.get('page_number'),
                    section_title=node.metadata.get('section_title'),
                    parent_id=parent_id,
                    order=idx,
                    metadata={
                        'source_format': source_format,
                        'llamaindex_id': node.node_id,
                        'llamaindex_metadata': node.metadata,
                    },
                ))

            return nodes, True
        except Exception as e:
            logger.warning("LlamaIndex parsing failed: %s", e)
            return [], False

    # ── Shared utilities ─────────────────────────────────────────────────────

    def _split_markdown_by_headings(self, markdown: str) -> List[dict]:
        """Split markdown content into sections based on heading levels."""
        lines = markdown.split("\n")
        sections: List[dict] = []
        current_section: dict | None = None
        heading_stack: dict[int, str] = {}

        for line in lines:
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                if current_section and current_section["content"].strip():
                    sections.append(current_section)

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_stack[level] = title
                for l in list(heading_stack.keys()):
                    if l > level:
                        del heading_stack[l]
                breadcrumb = [heading_stack[l] for l in sorted(heading_stack.keys())]

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
                if "|" in line and "---" not in line:
                    current_section["table_count"] += 1

        if current_section and current_section["content"].strip():
            sections.append(current_section)
        return sections

    def _split_text_to_chunks(
        self,
        text: str,
        chunk_size: int = 400,
        overlap: int = 75,
    ) -> List[str]:
        """Split text into chunks of approximately chunk_size tokens."""
        if not text or not text.strip():
            return []

        chars_per_chunk = chunk_size * 4
        overlap_chars = overlap * 4

        sentences = re.split(r'(?<=[.!?。！？])\s+|\n\n+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return [text.strip()] if text.strip() else []

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_length + sentence_len > chars_per_chunk and current_chunk:
                chunks.append(" ".join(current_chunk))
                overlap_len = 0
                overlap_sentences: List[str] = []
                for s in reversed(current_chunk):
                    if overlap_len + len(s) > overlap_chars:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_len += len(s)
                current_chunk = overlap_sentences
                current_length = overlap_len
            current_chunk.append(sentence)
            current_length += sentence_len

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)
        return chunks

    def _refine_nodes(self, nodes: List[IngestedNode]) -> List[IngestedNode]:
        """Rule-based text refinement: fix OCR errors, normalize whitespace."""
        from app.services.ingestion.rule_based_refiner import rule_based_refiner

        id_map = {
            node.metadata.get('llamaindex_id'): node.node_id
            for node in nodes
            if node.metadata.get('llamaindex_id')
        }
        heading_stack: dict[int, str] = {}

        for idx, node in enumerate(nodes):
            original_text = node.text
            current_header = node.section_title

            try:
                cleaned_text, predicted_header = rule_based_refiner.refine_text(
                    original_text, current_header
                )
            except Exception as e:
                logger.warning("Rule-based refinement failed for node %d: %s", idx, e)
                cleaned_text, predicted_header = original_text, current_header

            node.text = cleaned_text

            if node.node_type == ParsedNodeType.SECTION:
                level_match = re.match(r'^(#+)', original_text)
                level = len(level_match.group(1)) if level_match else 1
                title = predicted_header or original_text.lstrip('#').strip()
                node.section_title = title
                heading_stack[level] = title
                for l in list(heading_stack.keys()):
                    if l > level:
                        del heading_stack[l]

            node.metadata['breadcrumb'] = [heading_stack[l] for l in sorted(heading_stack.keys())]

            li_parent_id = node.metadata.get('llamaindex_metadata', {}).get('parent_id')
            if li_parent_id and li_parent_id in id_map:
                node.parent_id = id_map[li_parent_id]

        return nodes

    def _infer_node_type(self, node) -> ParsedNodeType:
        """Infer node type from LlamaIndex node metadata."""
        text = getattr(node, 'text', '') or ''
        metadata = getattr(node, 'metadata', {}) or {}

        if metadata.get('node_type'):
            try:
                return ParsedNodeType(str(metadata['node_type']).lower())
            except ValueError:
                pass

        if '```' in text or 'def ' in text or 'class ' in text:
            return ParsedNodeType.CODE_BLOCK
        elif '|' in text and text.count('\n') < 20:
            return ParsedNodeType.TABLE
        elif text.startswith('#') or text.startswith('##'):
            return ParsedNodeType.SECTION
        else:
            return ParsedNodeType.PARAGRAPH

    def _calculate_quality_score(self, nodes: List[IngestedNode], markdown_chars: int) -> float:
        """Calculate parse quality score (0-1)."""
        if not nodes:
            return 0.0

        avg_node_length = sum(len(n.text) for n in nodes) / len(nodes)
        length_score = min(avg_node_length / 500, 1.0)

        node_types = set(n.node_type for n in nodes)
        type_diversity = len(node_types) / len(ParsedNodeType)

        hierarchical_nodes = sum(1 for n in nodes if n.parent_id)
        hierarchy_score = min(hierarchical_nodes / len(nodes), 1.0)

        return min(max(
            length_score * 0.5 + type_diversity * 0.25 + hierarchy_score * 0.25,
            0.0,
        ), 1.0)

    def _extract_format(self, filename: str) -> str:
        """Extract file format from filename."""
        ext = os.path.splitext(filename.lower())[1].lstrip('.')
        format_map = {
            'pdf': 'pdf', 'docx': 'docx', 'doc': 'docx',
            'xlsx': 'xlsx', 'xls': 'xlsx', 'txt': 'text',
            'md': 'markdown', 'html': 'html', 'htm': 'html',
        }
        return format_map.get(ext, ext or 'unknown')
