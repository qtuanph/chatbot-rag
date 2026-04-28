"""
Abstract adapter base classes for parser, embedding, and vector store implementations.
Follows Kotaemo's adapter pattern for clean, swappable implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
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
    warnings: List[str] = None  # Non-fatal issues encountered
    node_count: int = 0  # Number of nodes extracted
    total_text_chars: int = 0  # Total character count in extracted text
    sections_data: List[Dict[str, Any]] = None  # Section records for PostgreSQL (RAG v2)

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.sections_data is None:
            self.sections_data = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = datetime.utcnow().isoformat()
        return data


@dataclass
class IngestedNode:
    """Represents a single parsed node from a document."""

    node_id: str
    document_id: str
    text: str
    node_type: ParsedNodeType
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    parent_id: Optional[str] = None  # For hierarchical documents
    order: int = 0  # Position in parent or document
    metadata: Dict[str, Any] = None  # Custom metadata (headings, tables, coordinates, etc.)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
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
    Implementations: DoclingParser, ClassicParser, etc.
    """

    @abstractmethod
    def parse(
        self,
        filename: str,
        content: bytes,
    ) -> Tuple[List[IngestedNode], ParsingMetadata]:
        """
        Parse document content into structured nodes.

        Args:
            filename: Name of the document (for format detection)
            content: Raw file bytes

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
    embedding: List[float]
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
    def embed(self, text: str, normalize: bool = True) -> List[float]:
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
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> List[List[float]]:
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
    metadata: Dict[str, Any]


class BaseVectorStore(ABC):
    """
    Abstract base class for vector store implementations.
    Implementations: QdrantVectorStore, ChromaVectorStore, etc.
    """

    @abstractmethod
    def health_check(self) -> bool:
        """Check if vector store is reachable and healthy."""
        pass

    @abstractmethod
    def store(
        self,
        document_id: str,
        nodes: List[IngestedNode],
        embeddings: List[List[float]],
    ) -> List[str]:
        """
        Store document nodes with embeddings.

        Args:
            document_id: ID of the document
            nodes: List of IngestedNode objects
            embeddings: List of embedding vectors (must match nodes length)

        Returns:
            List of stored node IDs

        Raises:
            VectorStoreException: If store operation fails
        """
        pass

    @abstractmethod
    def retrieve(
        self,
        query_vector: List[float],
        top_k: int = 5,
        document_id_filter: Optional[str] = None,
        document_ids_filter: Optional[List[str]] = None,
        section_ids_filter: Optional[List[str]] = None,
    ) -> List[RetrievedDocument]:
        """
        Retrieve top-k documents by vector similarity.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            document_id_filter: Optional filter to specific document
            document_ids_filter: Optional filter to multiple document IDs
            section_ids_filter: Optional filter to multiple section IDs

        Returns:
            List of RetrievedDocument objects with scores

        Raises:
            VectorStoreException: If retrieve fails
        """
        pass

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """
        Delete all vectors for a document.

        Args:
            document_id: ID of document to delete

        Returns:
            True if deletion succeeded, False otherwise

        Raises:
            VectorStoreException: If deletion fails
        """
        pass
