from __future__ import annotations

from app.adapters.base import BaseEmbedding
from app.adapters.embeddings.gemini import GeminiEmbedding
from app.core.config import settings


def build_embedding_service() -> BaseEmbedding:
    model = (settings.embedding_model or "").strip().lower()

    if model in {"gemini", "gemini-embedding-001", "models/gemini-embedding-001"}:
        return GeminiEmbedding(
            model_name="models/gemini-embedding-001",
            normalize=settings.embedding_normalize,
            output_dimensionality=768,
        )

    raise ValueError(
        "Unsupported EMBEDDING_MODEL. Use gemini-embedding-001 for current lightweight setup."
    )
