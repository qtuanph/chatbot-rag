"""Cohere cross-encoder reranker as a LlamaIndex node postprocessor."""

from __future__ import annotations

import httpx
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.core.config import settings


class CohereRerankerPostprocessor(BaseNodePostprocessor):
    """Rerank retrieved nodes using Cohere API."""

    top_k: int = settings.retrieval_rerank_top_k
    base_url: str = "https://api.cohere.com"
    model_name: str = "rerank-multilingual-v3.0"
    api_key: str = ""
    timeout: float = 30.0

    async def _postprocess_nodes(self, nodes: list[NodeWithScore], query_bundle: QueryBundle) -> list[NodeWithScore]:
        if not nodes:
            return nodes

        documents = [{"text": n.node.text} for n in nodes]
        payload = {
            "model": self.model_name,
            "query": query_bundle.query_str,
            "documents": documents,
            "top_n": self.top_k,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        target_url = f"{self.base_url.rstrip('/')}/v1/rerank"

        retries = 3
        backoff = 2
        resp = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(target_url, json=payload, headers=headers)
                    resp.raise_for_status()
                    break
            except Exception:
                if attempt == retries - 1:
                    raise
                import asyncio

                await asyncio.sleep(backoff**attempt)

        if resp is None:
            return nodes
        data = resp.json()

        results = data.get("results", [])
        ranked = []
        for item in results:
            idx = item["index"]
            nodes[idx].score = float(item.get("relevance_score", 0.0))
            ranked.append(nodes[idx])
        return ranked
