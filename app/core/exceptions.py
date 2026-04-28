"""
Custom exception hierarchy for the chatbot-rag application.
Enables clear error handling, logging, and recovery strategies across layers.
"""


class ChatbotRAGException(Exception):
    """Base exception for all chatbot-rag errors."""

    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class IngestionException(ChatbotRAGException):
    """Base exception for ingestion-related errors."""

    pass


class ParsingException(IngestionException):
    """Raised when document parsing fails."""

    pass


class HierarchyValidationException(IngestionException):
    """Raised when node hierarchy validation fails (orphaned nodes, cycles, etc.)."""

    pass


class EmbeddingException(IngestionException):
    """Raised when text embedding fails."""

    pass


class VectorStoreException(IngestionException):
    """Base exception for vector store operations."""

    pass


class VectorStoreConnectionException(VectorStoreException):
    """Raised when unable to connect to vector store (e.g., Qdrant)."""

    pass


class VectorStoreOperationException(VectorStoreException):
    """Raised when vector store insert/retrieve/delete operations fail."""

    pass


class StorageException(ChatbotRAGException):
    """Base exception for storage layer errors."""

    pass


class DocumentStoreException(StorageException):
    """Raised when document metadata store operations fail."""

    pass


class RetrievalException(ChatbotRAGException):
    """Raised when retrieval pipeline fails (reranker, BM25 encoding, query expansion)."""

    pass


class ChatException(ChatbotRAGException):
    """Base exception for chat-related errors."""

    pass
