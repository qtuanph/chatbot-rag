"""
Vector Store Factory: Thread-safe singleton pattern for vector store initialization.

This module provides a cached factory function for building vector store instances,
following the same pattern as app/services/rag.py.
"""

from functools import lru_cache

from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.adapters.embeddings import build_embedding_service
from app.core.config import settings


@lru_cache(maxsize=1)
def build_vector_store() -> QdrantVectorStore:
    """
    Build and cache a vector store instance.

    This function is thread-safe and ensures only one instance exists per process.
    The embedding service is also cached via its own factory.

    Returns:
        QdrantVectorStore: Configured vector store instance
    """
    embedding_service = build_embedding_service()
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=embedding_service.get_dimension(),
        timeout=settings.qdrant_timeout,
    )
