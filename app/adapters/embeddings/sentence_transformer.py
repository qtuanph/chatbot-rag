"""
SentenceTransformer Embedding Adapter — Remote Client.
Calls the standalone AI-Engine service for inference.
"""

import logging
import httpx
from typing import List

from app.adapters.base import BaseEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedding(BaseEmbedding):
    """
    Remote embedding adapter that calls the AI-Engine service.
    Keeps the same interface but offloads computation.
    """

    def __init__(
        self,
        model_name: str | None = None,
        normalize: bool = True,
        batch_size: int = 32,
        query_prefix: str = "",
        passage_prefix: str = "",
    ):
        self.model_name = model_name or settings.embedding_hf_model
        self.normalize = normalize
        self.batch_size = batch_size
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.base_url = settings.ai_engine_url.rstrip("/")
        self._dim = settings.embedding_vector_size

    def get_dimension(self) -> int:
        return self._dim

    async def embed(self, text: str, normalize: bool = True) -> List[float]:
        """Embed a single text string via remote call."""
        results = await self.embed_batch([text], batch_size=1, normalize=normalize)
        return results[0] if results else []

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> List[List[float]]:
        """Embed multiple texts via AI-Engine remote call."""
        if not texts:
            return []

        # Apply passage prefix if this is for ingestion
        if self.passage_prefix:
            texts = [self.passage_prefix + t for t in texts]

        async with httpx.AsyncClient(timeout=settings.ai_stream_timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={
                        "texts": texts,
                        "batch_size": batch_size or self.batch_size,
                        "normalize": normalize and self.normalize,
                        "task_type": "passage" if self.passage_prefix else "query",
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["embeddings"]
            except Exception as e:
                logger.error(f"AI-Engine /embed failed: {e}")
                raise

    async def embed_query(self, text: str) -> List[float]:
        """Embed a query text via remote call."""
        # Query prefix is handled by the server or here
        prefixed = self.query_prefix + text if self.query_prefix else text
        async with httpx.AsyncClient(timeout=settings.ai_http_timeout_refine) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={"texts": [prefixed], "batch_size": 1, "normalize": self.normalize, "task_type": "query"},
                )
                response.raise_for_status()
                data = response.json()
                return data["embeddings"][0]
            except Exception as e:
                logger.error(f"AI-Engine /embed query failed: {e}")
                raise

    def unload(self) -> None:
        """No-op for remote client."""
        pass
