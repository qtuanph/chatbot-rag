"""Wrap AITeamVN embedding model as LlamaIndex BaseEmbedding."""

from __future__ import annotations

from typing import Any, List

from llama_index.core.embeddings import BaseEmbedding

from app.adapters.embeddings.sentence_transformer import SentenceTransformerEmbedding
from app.core.config import settings


class AITeamVNEmbedding(BaseEmbedding):
    """Wrap AITeamVN/Vietnamese_Embedding_v2 as a LlamaIndex BaseEmbedding."""

    def __init__(
        self,
        model_name: str | None = None,
        embed_batch_size: int = 32,
        **kwargs: Any,
    ) -> None:
        self._embedder = SentenceTransformerEmbedding(
            model_name=model_name or settings.embedding_hf_model,
            normalize=settings.embedding_normalize,
            batch_size=embed_batch_size,
            query_prefix=settings.embedding_query_prefix,
            passage_prefix=settings.embedding_passage_prefix,
        )
        super().__init__(
            model_name=model_name or settings.embedding_hf_model,
            embed_batch_size=embed_batch_size,
            **kwargs,
        )

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._embedder.embed(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return await self._embedder.embed_batch(texts, batch_size=self.embed_batch_size)

    def _get_text_embedding(self, text: str) -> List[float]:
        raise NotImplementedError("Synchronous embedding not supported; use async methods")

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("Synchronous embedding not supported; use async methods")

    def get_dimension(self) -> int:
        return self._embedder.get_dimension()
