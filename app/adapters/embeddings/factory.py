from __future__ import annotations

from app.adapters.base import BaseEmbedding
from app.adapters.embeddings.tei_embedding import TEIEmbedding
from app.core.config import settings


def build_embedding_service() -> BaseEmbedding:
    """
    Factory: returns the TEI remote embedding adapter.

    Model: Alibaba-NLP/gte-multilingual-base — 768-dim, 8192 context,
    served via Text Embeddings Inference (TEI) container.

    IMPORTANT: changing the model changes the vector dimension.
    Drop Qdrant data on model switch:
      docker volume rm chatbot-rag_qdrantdata && docker compose up -d
    """
    return TEIEmbedding(
        model_name=settings.embedding_hf_model,
        batch_size=settings.embedding_batch_size,
    )
