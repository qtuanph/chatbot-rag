"""Local HTTP reranker postprocessor compatible with the legacy `/rerank` contract."""

from __future__ import annotations

import httpx
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.core.config import settings


class TEIRerankerPostprocessor(BaseNodePostprocessor):
    """Rerank retrieved nodes using the local `/rerank` endpoint."""

    top_k: int = settings.retrieval_rerank_top_k
    base_url: str = settings.ai_reranker_url

    async def _postprocess_nodes(self, nodes: list[NodeWithScore], query_bundle: QueryBundle) -> list[NodeWithScore]:
        if not nodes:
            return nodes

        texts = [n.node.text for n in nodes]

        retries = 3
        backoff = 2
        resp = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=settings.ai_reranker_timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/rerank",
                        json={"query": query_bundle.query_str, "texts": texts, "raw_scores": False},
                    )
                    resp.raise_for_status()
                    break
            except Exception:
                if attempt == retries - 1:
                    raise
                import asyncio

                await asyncio.sleep(backoff**attempt)

        if resp is None:
            return nodes
        scores = resp.json()

        ranked = []
        for item in sorted(scores, key=lambda x: x["score"], reverse=True)[: self.top_k]:
            idx = item["index"]
            nodes[idx].score = item["score"]
            ranked.append(nodes[idx])
        return ranked
