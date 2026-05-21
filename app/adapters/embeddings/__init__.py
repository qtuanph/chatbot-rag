"""Embeddings adapters module."""

from app.adapters.embeddings.factory import build_embedding_service
from app.adapters.embeddings.tei_embedding import TEIEmbedding

__all__ = ["build_embedding_service", "TEIEmbedding"]
