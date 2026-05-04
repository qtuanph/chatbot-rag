"""
Parser Manager: Selects appropriate parser based on configuration.
Docling + PaddleOCR is the primary parser for ALL document formats.
Classic parser is fallback when Docling is unavailable.
"""

import logging
from app.adapters.base import (
    IngestedNode,
    ParsingMetadata,
)
from app.adapters.parsers.docling import DoclingParser
from app.adapters.parsers.classic import ClassicParser
from app.core.config import settings
from app.core.exceptions import ParsingException

logger = logging.getLogger(__name__)


class ParserManager:
    """
    Manages parser selection and orchestration.
    - Primary: Docling + PaddleOCR (PDF, DOCX, images, etc.)
    - Fallback: Classic parser (when Docling unavailable)
    """

    def __init__(self):
        """Initialize parsers."""
        self.classic_parser = ClassicParser()
        self.docling_parser = None
        self.primary_parser_name = settings.ingestion_engine

        if self.primary_parser_name == "docling":
            try:
                self.docling_parser = DoclingParser(fallback_parser=self.classic_parser)
                logger.info("ParserManager: Docling + PaddleOCR ready (all formats)")
            except Exception as e:
                logger.critical(
                    "ParserManager: Docling+PaddleOCR FAILED to initialize: %s. "
                    "PDF/image OCR will NOT work! Fix: pip install rapidocr_onnxruntime",
                    e,
                )
                self.docling_parser = None
        else:
            logger.info("ParserManager: Classic parser only (ingestion_engine=%s)", self.primary_parser_name)

    def parse(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
    ) -> tuple[list[IngestedNode], ParsingMetadata]:
        """
        Parse document using configured parser.

        Args:
            filename: Document filename
            content: Raw file bytes
            document_id: UUID of the document (for node identity)

        Returns:
            Tuple of (IngestedNode list, ParsingMetadata)

        Raises:
            ParsingException: If all parsers fail
        """
        if self.docling_parser:
            try:
                return self.docling_parser.parse(filename, content, document_id)
            except ParsingException:
                raise
        else:
            try:
                return self.classic_parser.parse(filename, content, document_id)
            except ParsingException as e:
                logger.error("Classic parser failed: %s", e.message)
                raise
