"""
Adapter base classes — only parsing types retained.
Embedding, vector store, and retrieval adapters replaced by LlamaIndex.
"""

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum


class ParsedNodeType(str, Enum):
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    PAGE = "page"


@dataclass
class ParsingMetadata:
    engine_used: str
    source_format: str
    docling_used: bool = False
    fallback_used: bool = False
    quality_score: float = 1.0
    parse_time_ms: float = 0.0
    warnings: list[str] = None
    node_count: int = 0
    total_text_chars: int = 0
    sections_data: list[dict[str, Any]] = None
    raw_md_content: str = ""

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.sections_data is None:
            self.sections_data = []

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        return data


@dataclass
class IngestedNode:
    node_id: str
    document_id: str
    text: str
    node_type: ParsedNodeType
    page_number: int | None = None
    section_title: str | None = None
    parent_id: str | None = None
    order: int = 0
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "document_id": self.document_id,
            "text": self.text,
            "node_type": self.node_type.value if isinstance(self.node_type, ParsedNodeType) else self.node_type,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "parent_id": self.parent_id,
            "order": self.order,
            "metadata": self.metadata,
        }


class BaseParser(ABC):
    @abstractmethod
    async def parse(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
    ) -> tuple[list[IngestedNode], ParsingMetadata]:
        pass
