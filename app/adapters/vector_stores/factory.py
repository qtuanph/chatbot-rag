"""
Vector Store Factory: Thread-safe singleton pattern for vector store initialization.

This module provides a cached factory function for building vector store instances,
following the same pattern as app/services/rag.py.
"""

from functools import lru_cache

from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.config import settings


@lru_cache(maxsize=1)
def build_vector_store() -> QdrantVectorStore:
    """
    Build and cache a vector store instance.

    This function is thread-safe and ensures only one instance exists per process.
    The vector size comes from configuration so this factory does not need
    to instantiate the embedding model during tree/detail reads.

    Returns:
        QdrantVectorStore: Configured vector store instance
    """
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
        timeout=settings.qdrant_timeout,
    )
