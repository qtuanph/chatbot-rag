"""
Abstract adapter base classes for parser, embedding, and vector store implementations.
Follows Kotaemo's adapter pattern for clean, swappable implementations.
"""

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum


class ParsedNodeType(str, Enum):
    """Types of parsed document nodes."""

    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    PAGE = "page"


@dataclass
class ParsingMetadata:
    """Metadata about the parsing process."""

    engine_used: str  # "docling+items", "docling+sections", "classic"
    source_format: str  # "pdf", "docx", "txt", "markdown", "xlsx"
    docling_used: bool = False  # Whether Docling was used
    fallback_used: bool = False  # Whether fallback parser was triggered
    quality_score: float = 1.0  # 0.0–1.0 based on parse completeness
    parse_time_ms: float = 0.0  # Milliseconds spent parsing
    warnings: list[str] = None  # Non-fatal issues encountered
    node_count: int = 0  # Number of nodes extracted
    total_text_chars: int = 0  # Total character count in extracted text
    sections_data: list[dict[str, Any]] = None  # Section records for PostgreSQL (RAG v2)
    raw_md_content: str = ""  # Full raw markdown output from OCR for S3 persistence

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.sections_data is None:
            self.sections_data = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        return data


@dataclass
class IngestedNode:
    """Represents a single parsed node from a document."""

    node_id: str
    document_id: str
    text: str
    node_type: ParsedNodeType
    page_number: int | None = None
    section_title: str | None = None
    parent_id: str | None = None  # For hierarchical documents
    order: int = 0  # Position in parent or document
    metadata: dict[str, Any] = None  # Custom metadata (headings, tables, coordinates, etc.)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage/transmission."""
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
    """
    Abstract base class for document parsers.
    Implementations: LlamaParseParser, etc.
    """

    @abstractmethod
    async def parse(
        self,
        filename: str,
        content: bytes,
        document_id: str | None = None,
    ) -> tuple[list[IngestedNode], ParsingMetadata]:
        """
        Parse document content into structured nodes.

        Args:
            filename: Name of the document (for format detection)
            content: Raw file bytes
            document_id: UUID of the document (for node identity)

        Returns:
            Tuple of (list of IngestedNode, ParsingMetadata)

        Raises:
            ParsingException: If parsing fails irreversibly
        """
        pass


@dataclass
class EmbeddingResult:
    """Result of embedding operation."""

    text: str
    embedding: list[float]
    dimension: int
    model: str


class BaseEmbedding(ABC):
    """
    Abstract base class for text embedding implementations.
    Implementations: SentenceTransformerEmbedding, provider-specific adapters, etc.
    """

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the embedding vector dimension."""
        pass

    @abstractmethod
    async def embed(self, text: str, normalize: bool = True) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: Text to embed
            normalize: Whether to normalize embeddings (L2 norm)

        Returns:
            List of floats representing the embedding vector

        Raises:
            EmbeddingException: If embedding fails
        """
        pass

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Embed multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            normalize: Whether to normalize embeddings

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingException: If embedding fails
        """
        pass


@dataclass
class RetrievedDocument:
    """Result of vector store retrieval."""

    node_id: str
    document_id: str
    text: str
    score: float  # Relevance score (0-1 or 0-100 depending on store)
    metadata: dict[str, Any]


class BaseVectorStore(ABC):
    """
    Abstract base class for vector store implementations.
    Implementations: QdrantVectorStore, ChromaVectorStore, etc.
    """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if vector store is reachable and healthy."""
        pass

    @abstractmethod
    async def store(
        self,
        document_id: str,
        nodes: list[IngestedNode],
        embeddings: list[list[float]],
        sparse_embeddings: list[Any] | None = None,
    ) -> list[str]:
        """
        Store document nodes with embeddings.
        """
        pass

    @abstractmethod
    async def retrieve(
        self,
        query_vectors: list[list[float]],
        top_k: int = 5,
        document_ids_filter: list[str] | None = None,
        sparse_vectors: list[Any] | None = None,
    ) -> list[RetrievedDocument]:
        """
        Retrieve top-k documents by vector similarity.
        """
        pass

    @abstractmethod
    async def delete(self, document_id: str) -> bool:
        """
        Delete all vectors for a document.
        """
        pass
