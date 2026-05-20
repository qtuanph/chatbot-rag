"""
SentenceTransformer Embedding Adapter — Remote Client.
Calls the standalone AI-Engine service for inference.
"""

import asyncio
import logging
import httpx
from typing import List

from app.adapters.base import BaseEmbedding
from app.core.config import settings

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        limits = httpx.Limits(
            max_connections=settings.ai_http_max_connections,
            max_keepalive_connections=settings.ai_http_keepalive_connections,
        )
        _shared_client = httpx.AsyncClient(
            timeout=settings.ai_stream_timeout,
            limits=limits,
        )
        logger.info(
            "Created shared httpx client (pool=%d, keepalive=%d)",
            settings.ai_http_max_connections,
            settings.ai_http_keepalive_connections,
        )
    return _shared_client


async def _retry_call(coro_factory, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning("Retry %d/%d after %.1fs: %s", attempt + 1, max_retries, delay, e)
                await asyncio.sleep(delay)
            else:
                raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503 and attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning("Retry %d/%d after %.1fs (503): %s", attempt + 1, max_retries, delay, e)
                await asyncio.sleep(delay)
            else:
                raise


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

        if self.passage_prefix:
            texts = [self.passage_prefix + t for t in texts]

        async def _do_embed():
            client = _get_client()
            response = await client.post(
                f"{self.base_url}/embed",
                json={
                    "texts": texts,
                    "batch_size": batch_size or self.batch_size,
                    "normalize": normalize and self.normalize,
                    "task_type": "passage" if self.passage_prefix else "query",
                },
                timeout=settings.ai_stream_timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"]

        try:
            return await _retry_call(_do_embed)
        except Exception as e:
            logger.error("AI-Engine /embed failed after retries: %s", e)
            raise

    async def embed_query(self, text: str) -> List[float]:
        """Embed a query text via remote call."""
        prefixed = self.query_prefix + text if self.query_prefix else text

        async def _do_embed_query():
            client = _get_client()
            response = await client.post(
                f"{self.base_url}/embed",
                json={"texts": [prefixed], "batch_size": 1, "normalize": self.normalize, "task_type": "query"},
                timeout=settings.ai_http_timeout_refine,
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]

        try:
            return await _retry_call(_do_embed_query)
        except Exception as e:
            logger.error("AI-Engine /embed query failed after retries: %s", e)
            raise

    def unload(self) -> None:
        """No-op for remote client."""
        pass
