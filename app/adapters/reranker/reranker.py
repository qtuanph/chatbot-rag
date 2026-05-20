"""
Vietnamese Cross-Encoder Reranker — Remote Client.
Calls the standalone AI-Engine service for precision re-ranking.
"""

from __future__ import annotations

import asyncio
import logging
import httpx
from functools import lru_cache

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
            "Created shared httpx client for reranker (pool=%d, keepalive=%d)",
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


@lru_cache(maxsize=1)
def get_reranker() -> VietnameseReranker:
    """Get or create the singleton reranker instance."""
    return VietnameseReranker()


class VietnameseReranker:
    """
    Remote reranker adapter that calls the AI-Engine service.
    """

    def __init__(self):
        self.base_url = settings.ai_engine_url.rstrip("/")
        logger.info("Reranker client initialized (target=%s)", self.base_url)

    async def rerank(
        self,
        query: str,
        documents: list,
        text_attr: str = "full_text",
        top_k: int | None = None,
    ) -> list:
        """Re-rank documents via AI-Engine remote call."""
        if not documents:
            raise ValueError("Cannot rerank empty document list")

        top_k = top_k or settings.retrieval_rerank_top_k

        pairs = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get(text_attr) or ""
            else:
                text = getattr(doc, text_attr, None) or ""
            pairs.append({"query": query, "text": text})

        async def _do_rerank():
            client = _get_client()
            response = await client.post(f"{self.base_url}/rerank", json={"pairs": pairs, "top_k": top_k})
            response.raise_for_status()
            data = response.json()

            final_results = []
            for res in data["results"]:
                idx = res["index"]
                score = res["score"]
                doc = documents[idx]

                if isinstance(doc, dict):
                    doc["score"] = float(score)
                elif hasattr(doc, "score"):
                    doc.score = float(score)
                final_results.append(doc)

            return final_results

        try:
            return await _retry_call(_do_rerank)
        except Exception as e:
            logger.error("AI-Engine /rerank failed after retries: %s", e)
            raise

    def unload(self) -> None:
        """No-op for remote client."""
        pass
