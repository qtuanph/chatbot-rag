from __future__ import annotations

from app.adapters.base import BaseEmbedding
from app.adapters.embeddings.sentence_transformer import SentenceTransformerEmbedding
from app.core.config import settings


def build_embedding_service() -> BaseEmbedding:
    """
    Factory: returns the local embedding adapter (always sentence-transformer).

    Model: AITeamVN/Vietnamese_Embedding_v2 — 1024-dim, 8192-token context,
    BGE-M3 fine-tuned on 1.1M Vietnamese triplets (+16% Accuracy@1).
    Configurable via EMBEDDING_HF_MODEL env var if needed.

    IMPORTANT: changing the model changes the vector dimension.
    Drop Qdrant data on model switch:
      docker volume rm chatbot-rag_qdrantdata && docker compose up -d
    """
    return SentenceTransformerEmbedding(
        model_name=settings.embedding_hf_model,
        normalize=settings.embedding_normalize,
        batch_size=settings.embedding_batch_size,
        query_prefix=settings.embedding_query_prefix,
        passage_prefix=settings.embedding_passage_prefix,
    )
