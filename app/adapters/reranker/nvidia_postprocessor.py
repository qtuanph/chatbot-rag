"""NVIDIA NIM cross-encoder reranker as a LlamaIndex node postprocessor."""

from __future__ import annotations

import httpx
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.core.config import settings


class NvidiaRerankerPostprocessor(BaseNodePostprocessor):
    """Rerank retrieved nodes using NVIDIA NIM API."""

    top_k: int = settings.retrieval_rerank_top_k
    base_url: str = settings.nvidia_reranker_url
    model_name: str = settings.nvidia_reranker_model
    api_key: str = settings.nvidia_api_key
    timeout: float = settings.nvidia_reranker_timeout

    async def _postprocess_nodes(self, nodes: list[NodeWithScore], query_bundle: QueryBundle) -> list[NodeWithScore]:
        if not nodes:
            return nodes

        passages = [{"text": n.node.text} for n in nodes]
        payload = {
            "model": self.model_name,
            "query": {"text": query_bundle.query_str},
            "passages": passages,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        rankings = data.get("rankings", [])
        ranked = []
        for item in sorted(rankings, key=lambda x: x.get("logit", 0), reverse=True)[: self.top_k]:
            idx = item["index"]
            nodes[idx].score = float(item.get("logit", 0.0))
            ranked.append(nodes[idx])
        return ranked
