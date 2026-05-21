"""NVIDIA API Reranker — Online API for cross-encoder reranking."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class NvidiaReranker:
    """Calls NVIDIA NIM API for reranking."""

    def __init__(self) -> None:
        self.url = settings.nvidia_reranker_url
        self.model = settings.nvidia_reranker_model
        self.api_key = settings.nvidia_api_key
        self.timeout = settings.nvidia_reranker_timeout
        self._client: httpx.AsyncClient | None = None
        logger.info("NVIDIA Reranker client initialized (model=%s)", self.model)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
            self._client = httpx.AsyncClient(timeout=self.timeout, limits=limits)
        return self._client

    async def rerank(
        self,
        query: str,
        documents: list,
        text_attr: str = "full_text",
        top_k: int | None = None,
    ) -> list:
        """Re-rank documents via NVIDIA API."""
        if not documents:
            raise ValueError("Cannot rerank empty document list")

        top_k = top_k or settings.retrieval_rerank_top_k

        passages = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get(text_attr) or ""
            else:
                text = getattr(doc, text_attr, None) or ""
            passages.append({"text": text})

        payload = {
            "model": self.model,
            "query": {"text": query},
            "passages": passages,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        client = self._get_client()
        response = await client.post(self.url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        rankings = data.get("rankings", [])
        final_results = []
        for rank in rankings:
            idx = rank.get("index", 0)
            score = rank.get("logit", 0.0)
            doc = documents[idx]

            if isinstance(doc, dict):
                doc["score"] = float(score)
            elif hasattr(doc, "score"):
                doc.score = float(score)
            final_results.append(doc)

        return final_results[:top_k]

    def unload(self) -> None:
        if self._client:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    asyncio.create_task(self._client.aclose())
                else:
                    asyncio.run(self._client.aclose())
            except Exception:
                pass
            self._client = None
