"""
Docling Parser: Primary on-prem document parser using Docling + LlamaIndex.
Converts documents to Markdown, then builds hierarchical nodes.
Falls back to classic parser if conversion/parsing fails.
"""

import logging
import uuid
from typing import List, Tuple, Optional
from io import BytesIO
import os
import tempfile
import re

from app.adapters.base import (
    BaseParser,
    IngestedNode,
    ParsingMetadata,
    ParsedNodeType,
)
from app.core.exceptions import (
    ParsingException,
    ParsingFallbackException,
)
from app.services.ingestion.rule_based_refiner import rule_based_refiner
from app.core.hardware import hardware

logger = logging.getLogger(__name__)


class DoclingParser(BaseParser):
    """
    Primary parser: Docling (PDF/DOCX/HTML to Markdown) + LlamaIndex hierarchical parsing.
    Falls back to classic parser on failure.
    """

    def __init__(
        self,
        fallback_parser: Optional['BaseParser'] = None,
        min_quality_score: float = 0.5,
    ):
        """
        Initialize DoclingParser.
        
        Args:
            fallback_parser: Optional fallback parser for when Docling/LlamaIndex fail
            min_quality_score: Minimum quality score to accept parse result
        """
        self.fallback_parser = fallback_parser
        self.min_quality_score = min_quality_score
        self.docling_converter = None
        self.llamaindex_parser = None
        
        self._initialize_docling()
        self._initialize_llamaindex()

    def _select_ocr_backend(self):
        """
        Build EasyOCR options for Vietnamese + English documents.
        GPU is used automatically when detected by the hardware profile.
        easyocr must be installed (see requirements.txt).
        """
        from docling.datamodel.pipeline_options import EasyOcrOptions
        use_gpu = hardware.gpu_count > 0
        opts = EasyOcrOptions(lang=["vi", "en"], use_gpu=use_gpu)
        logger.info("OCR backend: EasyOCR [vi, en] gpu=%s", use_gpu)
        return opts

    def _initialize_docling(self) -> None:
        """Lazy-initialize Docling converter with best available OCR backend."""
        try:
            from docling.document_converter import (
                DocumentConverter,
                PdfFormatOption,
                ImageFormatOption,
            )
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            ocr_options = self._select_ocr_backend()

            pipeline_pdf = PdfPipelineOptions(
                do_ocr=False,              # Native PDF: extract embedded text directly (faster, no garbled chars)
                do_table_structure=True,   # Preserve table structure for technical docs
            )
            pipeline_pdf_scanned = PdfPipelineOptions(
                do_ocr=True,               # Scanned PDF fallback: use EasyOCR
                ocr_options=ocr_options,
                do_table_structure=True,
            )

            pipeline_image = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options,
                do_table_structure=True,
            )

            format_options = {
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_pdf),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_image),
            }

            self.docling_converter = DocumentConverter(format_options=format_options)
            logger.info("Docling DocumentConverter initialized with OCR langs: vie, eng")
        except ImportError:
            logger.warning("Docling not installed; will skip Docling parsing")
            self.docling_converter = None
        except Exception as e:
            logger.warning(f"Failed to initialize Docling with Vietnamese OCR config: {str(e)}")
            try:
                from docling.document_converter import DocumentConverter

                self.docling_converter = DocumentConverter()
                logger.info("Docling DocumentConverter initialized with default OCR settings")
            except Exception:
                logger.warning("Failed to initialize default Docling converter")
                self.docling_converter = None

    def _initialize_llamaindex(self) -> None:
        """Lazy-initialize LlamaIndex Markdown parser."""
        try:
            from llama_index.core.node_parser import MarkdownNodeParser
            self.llamaindex_parser = MarkdownNodeParser()
            logger.info("LlamaIndex MarkdownNodeParser initialized")
        except ImportError:
            logger.warning("LlamaIndex not installed; will skip LlamaIndex hierarchical parsing")
            self.llamaindex_parser = None
        except Exception as e:
            logger.warning(f"Failed to initialize LlamaIndex: {str(e)}")
            self.llamaindex_parser = None

    def parse(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[List[IngestedNode], ParsingMetadata]:
        """
        Parse document using Docling + LlamaIndex with fallback.
        
        Args:
            filename: Document filename (for format detection)
            content: Raw file bytes
        
        Returns:
            Tuple of (IngestedNode list, ParsingMetadata)
        
        Raises:
            ParsingException: If all parsing strategies fail irreversibly
        """
        import time
        start_time = time.time()
        
        # Determine source format from filename extension
        source_format = self._extract_format(filename)
        
        try:
            # Step 1: Try Docling conversion
            markdown_content, docling_used = self._convert_with_docling(filename, content)
            
            if markdown_content:
                # Step 2: Try LlamaIndex hierarchical parsing
                nodes, llamaindex_used = self._parse_markdown_with_llamaindex(
                    markdown_content=markdown_content,
                    document_id=filename,
                    source_format=source_format,
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
                        total_text_chars=sum(len(node.text) for node in nodes),
                        warnings=[],
                    )
                    logger.info(f"Parsed {filename} with Docling+LlamaIndex: {len(nodes)} nodes")
                    
                    # Step 3: Local AI Structural Audit & Refinement
                    try:
                        logger.info(f"Starting AI Structural Audit for {len(nodes)} nodes...")
                        
                        # ID Map to fix Parent/Child relationships
                        # LlamaIndex internal ID -> IngestedNode ID
                        id_map = {node.metadata.get('llamaindex_id'): node.node_id for node in nodes if node.metadata.get('llamaindex_id')}
                        
                        # Heading Stack to track breadcrumbs
                        # depth -> title
                        heading_stack = {}
                        
                        for node in nodes:
                            # 1. Structural Audit with AI
                            # Rule-based refiner fixes OCR errors and detects headers
                            original_text = node.text
                            original_header = node.section_title

                            cleaned_text, predicted_header = rule_based_refiner.refine_text(original_text, original_header)
                            
                            # Update node
                            node.text = cleaned_text
                            
                            # 2. Hierarchy Preservation
                            # If level is H1-H6, update the stack
                            if node.node_type == ParsedNodeType.SECTION:
                                # Try to detect level from text (# = 1, ## = 2)
                                level_match = re.match(r'^(#+)', original_text)
                                level = len(level_match.group(1)) if level_match else 1
                                
                                title = predicted_header or original_text.lstrip('#').strip()
                                node.section_title = title
                                heading_stack[level] = title
                                # Clear deeper levels
                                for l in list(heading_stack.keys()):
                                    if l > level: del heading_stack[l]
                            
                            # 3. Breadcrumb Enrichment
                            current_breadcrumb = [heading_stack[l] for l in sorted(heading_stack.keys())]
                            node.metadata['breadcrumb'] = current_breadcrumb
                            
                            # 4. Fix Parent ID
                            # If llama_id parent exists but points to old ID, remap it
                            li_parent_id = node.metadata.get('llamaindex_metadata', {}).get('parent_id')
                            if li_parent_id and li_parent_id in id_map:
                                node.parent_id = id_map[li_parent_id]

                        # No VRAM cleanup needed - rule-based refiner uses 0GB VRAM
                    except Exception as refine_err:
                        logger.error(f"AI Structural Audit failed: {refine_err}")
                        import traceback
                        logger.error(traceback.format_exc())

                    return nodes, metadata
        
        except Exception as e:
            logger.warning(f"Docling+LlamaIndex parsing failed for {filename}: {str(e)}")
        
        # Step 3: Try fallback parser if configured
        if self.fallback_parser:
            try:
                nodes, fallback_metadata = self.fallback_parser.parse(filename, content)
                
                if nodes:
                    fallback_metadata.fallback_used = True
                    fallback_metadata.parse_time_ms = (time.time() - start_time) * 1000
                    logger.info(f"Parsed {filename} with fallback parser: {len(nodes)} nodes")
                    return nodes, fallback_metadata
            except Exception as e:
                logger.warning(f"Fallback parser also failed for {filename}: {str(e)}")
        
        # All parsing strategies failed
        raise ParsingException(
            f"Failed to parse {filename}: Docling+LlamaIndex and fallback all failed",
            error_code="PARSING_ALL_STRATEGIES_FAILED",
            details={'filename': filename, 'source_format': source_format}
        )

    def _extract_format(self, filename: str) -> str:
        """Extract file format from filename."""
        ext = os.path.splitext(filename.lower())[1].lstrip('.')
        format_map = {
            'pdf': 'pdf',
            'docx': 'docx',
            'doc': 'docx',
            'xlsx': 'xlsx',
            'xls': 'xlsx',
            'txt': 'text',
            'md': 'markdown',
            'html': 'html',
            'htm': 'html',
        }
        return format_map.get(ext, ext or 'unknown')

    def _convert_with_docling(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[Optional[str], bool]:
        """
        Convert document to Markdown using Docling.
        
        Returns:
            Tuple of (markdown_string or None, docling_used boolean)
        """
        if not self.docling_converter:
            logger.debug("Docling not available; skipping Docling conversion")
            return None, False
        
        try:
            # Write content to temp file for Docling processing
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(filename)[1],
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Convert to DocumentVM
                result = self.docling_converter.convert(tmp_path)
                
                # Export as Markdown
                markdown_content = result.document.export_to_markdown()
                
                logger.debug(f"Docling converted {filename} to {len(markdown_content)} chars of Markdown")
                return markdown_content, True
            finally:
                os.unlink(tmp_path)
        
        except Exception as e:
            logger.warning(f"Docling conversion failed for {filename}: {str(e)}")
            return None, False

    def _parse_markdown_with_llamaindex(
        self,
        markdown_content: str,
        document_id: str,
        source_format: str,
    ) -> Tuple[List[IngestedNode], bool]:
        """
        Parse Markdown content into hierarchical nodes using LlamaIndex.
        
        Returns:
            Tuple of (nodes list, llamaindex_used boolean)
        """
        if not self.llamaindex_parser:
            logger.debug("LlamaIndex not available; skipping hierarchical parsing")
            return [], False
        
        try:
            from llama_index.core.schema import Document
            
            # Create LlamaIndex document
            doc = Document(text=markdown_content, metadata={'file_name': document_id})
            
            # Parse into nodes
            llamaindex_nodes = self.llamaindex_parser.get_nodes_from_documents([doc])
            
            # Convert to IngestedNode objects
            nodes = []
            for idx, node in enumerate(llamaindex_nodes):
                node_id = str(uuid.uuid4())
                node_type = self._infer_node_type(node)
                parent_id = None
                
                # Infer parent-child relationships from metadata
                if hasattr(node, 'relationships') and 'parent' in node.relationships:
                    parent_id = node.relationships['parent'].node_id
                
                ingested_node = IngestedNode(
                    node_id=node_id,
                    document_id=document_id,
                    text=node.get_content(),
                    node_type=node_type,
                    page_number=node.metadata.get('page_number'),
                    section_title=node.metadata.get('section_title'),
                    parent_id=parent_id,
                    order=idx,
                    metadata={
                        'source_format': source_format,
                        'llamaindex_id': node.node_id, # Store original ID for remapping
                        'llamaindex_metadata': node.metadata,
                    },
                )
                nodes.append(ingested_node)
            
            logger.debug(f"LlamaIndex parsed Markdown into {len(nodes)} hierarchical nodes")
            return nodes, True
        
        except Exception as e:
            logger.warning(f"LlamaIndex hierarchical parsing failed: {str(e)}")
            return [], False

    def _infer_node_type(self, node) -> ParsedNodeType:
        """Infer node type from LlamaIndex node metadata."""
        # Try to guess from metadata or text patterns
        text = getattr(node, 'text', '') or ''
        metadata = getattr(node, 'metadata', {}) or {}
        
        # Check metadata hints
        if metadata.get('node_type'):
            node_type_str = str(metadata['node_type']).lower()
            try:
                return ParsedNodeType(node_type_str)
            except ValueError:
                pass
        
        # Heuristics based on content
        if '```' in text or 'def ' in text or 'class ' in text:
            return ParsedNodeType.CODE_BLOCK
        elif '|' in text and text.count('\n') < 20:
            return ParsedNodeType.TABLE
        elif text.startswith('#') or text.startswith('##'):
            return ParsedNodeType.SECTION
        else:
            return ParsedNodeType.PARAGRAPH

    def _calculate_quality_score(self, nodes: List[IngestedNode], markdown_chars: int) -> float:
        """
        Calculate parse quality score (0-1).
        Based on node count, text length, and diversity.
        """
        if not nodes:
            return 0.0
        
        # Base score: more nodes and more characters is better
        avg_node_length = sum(len(node.text) for node in nodes) / len(nodes) if nodes else 0
        length_score = min(avg_node_length / 500, 1.0)  # Normalize to 0-1
        
        # Diversity score: mix of node types
        node_types = set(node.node_type for node in nodes)
        type_diversity = len(node_types) / len(ParsedNodeType)
        
        # Hierarchy score: nodes with parent_id indicate hierarchy
        hierarchical_nodes = sum(1 for n in nodes if n.parent_id)
        hierarchy_score = min(hierarchical_nodes / len(nodes), 1.0) if nodes else 0.0
        
        # Weighted average
        quality_score = (
            length_score * 0.5 +
            type_diversity * 0.25 +
            hierarchy_score * 0.25
        )
        
        return min(max(quality_score, 0.0), 1.0)
