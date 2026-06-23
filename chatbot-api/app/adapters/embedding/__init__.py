"""Embedding adapter — unified OpenAI-compatible with auto-detect sparse support."""

from app.adapters.embedding.adapter import EmbeddingAdapter, EmbeddingCapability, EmbeddingResult

__all__ = [
    "EmbeddingAdapter",
    "EmbeddingCapability",
    "EmbeddingResult",
]
