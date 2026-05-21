"""
TEI Embedding Adapter — Remote Client for Text Embeddings Inference.
Calls the ai-embedding TEI service for vector generation.
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
            "Created shared httpx client for TEI embedding (pool=%d, keepalive=%d)",
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


class TEIEmbedding(BaseEmbedding):
    """
    Remote embedding adapter that calls the TEI ai-embedding service.
    TEI handles dynamic batching, normalization, and pooling internally.
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int = 32,
    ):
        self.model_name = model_name or settings.embedding_hf_model
        self.batch_size = batch_size
        self.base_url = settings.ai_embedding_url.rstrip("/")
        self._dim = settings.embedding_vector_size

    def get_dimension(self) -> int:
        return self._dim

    async def embed(self, text: str, normalize: bool = True) -> List[float]:
        """Embed a single text string via TEI remote call."""
        results = await self.embed_batch([text], batch_size=1)
        return results[0] if results else []

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int | None = None,
        normalize: bool = True,
    ) -> List[List[float]]:
        """Embed multiple texts via TEI remote call.

        TEI API: POST /embed {"inputs": [...]}
        Response: list of embedding vectors (already normalized by TEI)

        Automatically splits texts into sub-batches to respect TEI's MAX_BATCH_REQUESTS.
        """
        if not texts:
            return []

        effective_batch = batch_size or self.batch_size
        all_results: List[List[float]] = []

        for i in range(0, len(texts), effective_batch):
            chunk = texts[i : i + effective_batch]

            async def _do_embed():
                client = _get_client()
                response = await client.post(
                    f"{self.base_url}/embed",
                    json={"inputs": chunk},
                    timeout=settings.ai_stream_timeout,
                )
                response.raise_for_status()
                return response.json()

            results = await _retry_call(_do_embed)
            all_results.extend(results)

        return all_results

    async def embed_query(self, text: str) -> List[float]:
        """Embed a query text via TEI remote call."""

        async def _do_embed_query():
            client = _get_client()
            response = await client.post(
                f"{self.base_url}/embed",
                json={"inputs": text},
                timeout=settings.ai_http_timeout_refine,
            )
            response.raise_for_status()
            data = response.json()
            return data[0]

        try:
            return await _retry_call(_do_embed_query)
        except Exception as e:
            logger.error("TEI /embed query failed after retries: %s", e)
            raise

    def unload(self) -> None:
        """No-op for remote client."""
        pass
