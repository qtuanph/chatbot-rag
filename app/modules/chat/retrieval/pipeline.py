"""LlamaIndex-based retrieval pipeline — hybrid search + reranker (TEI or NVIDIA NIM)."""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core import VectorStoreIndex, QueryBundle
from llama_index.core.schema import NodeWithScore

from app.core.llama_index import get_vector_store
from app.adapters.reranker import get_reranker
from app.core.config import settings
from app.models.rag import RagContext, RagNode

logger = logging.getLogger(__name__)


async def retrieve_context(
    queries: list[str],
    session: Any = None,
    limit: int = 20,
    positive_point_ids: list[str] | None = None,
    negative_point_ids: list[str] | None = None,
) -> RagContext:
    """Retrieve context using LlamaIndex hybrid (dense + native BM25 RRF) + TEI reranker.

    Args:
        queries: List of query strings (expanded).
        limit: Max nodes to return after reranking.

    Returns:
        RagContext with scored nodes.
    """
    vector_store = get_vector_store()
    index = VectorStoreIndex.from_vector_store(vector_store)

    retriever = index.as_retriever(
        vector_store_query_mode="hybrid",
        similarity_top_k=settings.retrieval_hybrid_top_k,
        sparse_top_k=settings.retrieval_hybrid_top_k,
    )

    reranker = get_reranker(top_k=limit)

    all_nodes: list[NodeWithScore] = []
    seen_ids: set[str] = set()

    for query in queries:
        qb = QueryBundle(query_str=query)
        nodes = await retriever.aretrieve(query)
        nodes = await reranker.postprocess_nodes(nodes, qb)
        for n in nodes:
            if n.node.node_id not in seen_ids:
                seen_ids.add(n.node.node_id)
                all_nodes.append(n)

    all_nodes.sort(key=lambda n: n.score or 0, reverse=True)
    all_nodes = all_nodes[:limit]

    rag_nodes = []
    for n in all_nodes:
        meta = n.node.metadata or {}
        rag_nodes.append(
            RagNode(
                node_id=n.node.node_id,
                parent_id=meta.get("parent_id"),
                document_id=meta.get("document_id", ""),
                document_title=meta.get("document_title", meta.get("section_title", "")),
                heading=meta.get("section_title", ""),
                summary=meta.get("section_content", n.node.text[:200]),
                full_text=n.node.text,
                page_range=str(meta.get("page_number", "")),
                section_id=meta.get("section_id"),
                score=n.score or 0.0,
            )
        )

    return RagContext(nodes=rag_nodes, sections=None, confidence=None)
