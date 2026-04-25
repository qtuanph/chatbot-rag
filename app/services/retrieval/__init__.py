"""Retrieval & caching services for RAG."""

from app.services.retrieval.rag import (
    retrieve_context,
    build_answer,
    RagContext,
    RagNode,
    RagSection,
    invalidate_doc_ids_cache,
)
from app.services.retrieval.cache import QueryEmbeddingCache
from app.services.retrieval.bm25_index import (
    get_bm25_encoder,
    build_bm25_index_from_qdrant,
    update_bm25_index,
)
from app.services.retrieval.reranker import (
    get_reranker,
    VietnameseReranker,
)
from app.services.retrieval.query_expand import expand_query

__all__ = [
    # Core retrieval
    "retrieve_context",
    "build_answer",
    "invalidate_doc_ids_cache",
    "RagContext",
    "RagNode",
    "RagSection",
    # Cache
    "QueryEmbeddingCache",
    # BM25 hybrid search
    "get_bm25_encoder",
    "build_bm25_index_from_qdrant",
    "update_bm25_index",
    # Cross-encoder reranker
    "get_reranker",
    "VietnameseReranker",
    # Multi-query expansion
    "expand_query",
]
