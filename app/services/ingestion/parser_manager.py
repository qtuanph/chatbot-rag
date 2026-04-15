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
    - Primary: Docling+LlamaIndex if configured
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

    async def parse_async(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[List[IngestedNode], ParsingMetadata]:
        """
        Async version of parse().
        
        Args:
            filename: Document filename
            content: Raw file bytes
        
        Returns:
            Tuple of (IngestedNode list, ParsingMetadata)
        """
        if self.docling_parser:
            return await self.docling_parser.parse_async(filename, content)
        else:
            return await self.classic_parser.parse_async(filename, content)

    def get_available_parsers(self) -> List[str]:
        """Return list of available parser names."""
        parsers = ['classic']
        if self.docling_parser:
            parsers.insert(0, 'docling')
        return parsers

    def health_check(self) -> dict:
        """Return health status of parsers."""
        return {
            'primary_parser': self.primary_parser_name,
            'docling_available': self.docling_parser is not None,
            'classic_available': self.classic_parser is not None,
            'fallback_available': self.docling_parser is not None and self.docling_parser.fallback_parser is not None,
        }
