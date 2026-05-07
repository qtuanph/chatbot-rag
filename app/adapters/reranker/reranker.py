"""
Vietnamese Cross-Encoder Reranker — Remote Client.
Calls the standalone AI-Engine service for precision re-ranking.
"""

from __future__ import annotations

import logging
import httpx
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


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

        # Prepare pairs for the remote call
        pairs = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get(text_attr) or ""
            else:
                text = getattr(doc, text_attr, None) or ""
            pairs.append({"query": query, "text": text})

        async with httpx.AsyncClient(timeout=settings.ai_stream_timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/rerank", json={"pairs": pairs, "top_k": top_k})
                response.raise_for_status()
                data = response.json()

                # Re-map results back to original objects using the indices
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
            except Exception as e:
                logger.error(f"AI-Engine /rerank failed: {e}")
                raise

    def unload(self) -> None:
        """No-op for remote client."""
        pass
