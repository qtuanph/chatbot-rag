"""
Parser Manager: Selects appropriate parser based on configuration.
Handles graceful fallback if primary parser unavailable.
"""

import logging
from typing import List, Tuple
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
    - Primary: Docling (iterate_items → markdown fallback)
    - Secondary: Classic parser for fallback
    """

    def __init__(self):
        """Initialize available parsers."""
        self.classic_parser = ClassicParser()
        self.docling_parser = None
        self.primary_parser_name = settings.ingestion_engine
        
        # Initialize Docling parser with fallback to Classic
        if self.primary_parser_name == "docling":
            try:
                self.docling_parser = DoclingParser(fallback_parser=self.classic_parser)
                logger.info("ParserManager initialized with Docling+Classic fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize DoclingParser: {str(e)}; will use Classic only")
                self.docling_parser = None
        else:
            logger.info("ParserManager initialized with Classic parser only")

    def parse(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[List[IngestedNode], ParsingMetadata]:
        """
        Parse document using configured parser.
        
        Args:
            filename: Document filename
            content: Raw file bytes
        
        Returns:
            Tuple of (IngestedNode list, ParsingMetadata)
        
        Raises:
            ParsingException: If all parsers fail
        """
        if self.docling_parser:
            try:
                return self.docling_parser.parse(filename, content)
            except ParsingException as e:
                logger.warning(f"DoclingParser failed: {e.message}")
                # Fallback to Classic is handled within DoclingParser
                raise
        else:
            # Use Classic parser directly
            try:
                return self.classic_parser.parse(filename, content)
            except ParsingException as e:
                logger.error(f"Classic parser failed: {e.message}")
                raise

