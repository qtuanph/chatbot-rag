"""Wrap AITeamVN reranker as LlamaIndex BaseNodePostprocessor."""

from __future__ import annotations

from typing import Any, List, Optional

from llama_index.core.postprocessor import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.adapters.reranker.reranker import get_reranker
from app.core.config import settings


class AITeamVNReranker(BaseNodePostprocessor):
    """Wrap AITeamVN/Vietnamese_Reranker as a LlamaIndex node postprocessor."""

    def __init__(
        self,
        top_k: int | None = None,
        **kwargs: Any,
    ) -> None:
        self._top_k = top_k or settings.retrieval_rerank_top_k
        self._reranker = get_reranker()
        super().__init__(**kwargs)

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """Postprocess nodes synchronously (not used — use async in production)."""
        return nodes

    async def apostprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """Async reranking via AITeamVN cross-encoder."""
        if not nodes or not query_bundle:
            return nodes

        query = query_bundle.query_str
        docs = [
            {
                "text": n.node.get_content(),
                "full_text": n.node.get_content(),
                "score": n.score or 0.0,
            }
            for n in nodes
        ]

        reranked = await self._reranker.rerank(query, docs, text_attr="full_text", top_k=self._top_k)

        # Re-index scores back to nodes
        score_map = {d["text"]: d["score"] for d in reranked}
        for n in nodes:
            content = n.node.get_content()
            if content in score_map:
                n.score = score_map[content]

        # Sort by score descending
        nodes.sort(key=lambda n: n.score or 0.0, reverse=True)
        return nodes[: self._top_k]
