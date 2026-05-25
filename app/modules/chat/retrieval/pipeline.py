"""LlamaIndex-based retrieval pipeline — hybrid search + reranker (TEI or NVIDIA NIM)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from llama_index.core import QueryBundle, Settings, VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.core.postprocessor import LongContextReorder
from llama_index.core.schema import TextNode
from qdrant_client.http import models as rest

from app.core.llama_index import get_vector_store
from app.adapters.reranker import get_reranker
from app.core.config import settings
from app.models.rag import RagContext, RagNode

logger = logging.getLogger(__name__)


def _extract_text_and_metadata_from_payload(payload: dict[str, Any], text_key: str) -> tuple[str, dict[str, Any]]:
    """Extract usable text/metadata from Qdrant payload written by LlamaIndex.

    Newer payloads may not expose plain `text`; instead text/metadata lives in
    `_node_content` JSON. This helper normalizes both shapes.
    """
    text = payload.get(text_key) or payload.get("text") or ""
    metadata = {k: v for k, v in payload.items() if k not in {text_key, "text"}}

    if text:
        return str(text), metadata

    raw_node = payload.get("_node_content")
    if isinstance(raw_node, str) and raw_node:
        try:
            parsed = json.loads(raw_node)
            parsed_text = parsed.get("text") or ""
            parsed_meta = parsed.get("metadata") or {}
            if isinstance(parsed_meta, dict):
                merged_meta = dict(parsed_meta)
                merged_meta.update(metadata)
                metadata = merged_meta
            text = str(parsed_text or "")
        except Exception:
            pass

    return str(text), metadata


async def _hybrid_retrieve_via_qdrant(query: str, limit: int) -> list[NodeWithScore]:
    """Run hybrid retrieval directly via qdrant-client (dense + sparse fusion)."""
    vector_store = get_vector_store()
    aclient = vector_store._aclient
    if aclient is None:
        raise RuntimeError("Qdrant async client is not initialized")
    collection_name = vector_store.collection_name

    exists = await aclient.collection_exists(collection_name=collection_name)
    if not exists:
        await aclient.create_collection(
            collection_name=collection_name,
            vectors_config={
                vector_store.dense_vector_name: rest.VectorParams(
                    size=settings.embedding_vector_size,
                    distance=rest.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                vector_store.sparse_vector_name: rest.SparseVectorParams(),
            },
        )
        logger.warning(
            "Qdrant collection '%s' did not exist. Auto-created empty collection; retrieval will be empty until ingestion finishes.",
            collection_name,
        )
        return []

    dense_vector = await Settings.embed_model.aget_query_embedding(query)
    sparse_indices, sparse_values = await asyncio.to_thread(vector_store._sparse_query_fn, [query])
    sparse_vector = rest.SparseVector(indices=sparse_indices[0], values=sparse_values[0])

    response = await aclient.query_points(
        collection_name=collection_name,
        prefetch=[
            rest.Prefetch(
                query=dense_vector,
                using=vector_store.dense_vector_name,
                limit=settings.retrieval_hybrid_top_k,
            ),
            rest.Prefetch(
                query=sparse_vector,
                using=vector_store.sparse_vector_name,
                limit=settings.retrieval_hybrid_top_k,
            ),
        ],
        query=rest.FusionQuery(fusion=rest.Fusion.RRF),
        with_payload=True,
        with_vectors=False,
        limit=limit,
    )

    nodes: list[NodeWithScore] = []
    for point in response.points:
        payload = point.payload or {}
        text, metadata = _extract_text_and_metadata_from_payload(payload, vector_store.text_key)
        node = TextNode(id_=str(point.id), text=text, metadata=metadata)
        nodes.append(NodeWithScore(node=node, score=float(point.score or 0.0)))
    return nodes


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
    index = VectorStoreIndex.from_vector_store(vector_store) if not settings.retrieval_hybrid_enabled else None
    retriever = None
    if index is not None:
        retriever = index.as_retriever(similarity_top_k=settings.retrieval_hybrid_top_k)

    reranker = get_reranker(top_k=limit)
    reorder = LongContextReorder() if settings.retrieval_long_context_reorder_enabled else None

    all_nodes: list[NodeWithScore] = []
    seen_ids: set[str] = set()

    for query in queries:
        qb = QueryBundle(query_str=query)
        if settings.retrieval_hybrid_enabled:
            nodes = await _hybrid_retrieve_via_qdrant(query=query, limit=settings.retrieval_hybrid_top_k)
        else:
            if retriever is None:
                raise RuntimeError("Dense retriever is not initialized")
            nodes = await retriever.aretrieve(query)
        try:
            reranked_nodes = await reranker.postprocess_nodes(nodes, qb)
            if reranked_nodes:
                nodes = reranked_nodes
            else:
                logger.info("Reranker returned empty nodes for query='%s'; fallback to pre-rerank nodes.", query)
        except Exception:
            logger.warning("Reranker failed for query='%s'; fallback to pre-rerank nodes.", query, exc_info=True)
        if reorder is not None:
            nodes = reorder.postprocess_nodes(nodes, qb)
        for n in nodes:
            if n.node.node_id not in seen_ids:
                seen_ids.add(n.node.node_id)
                all_nodes.append(n)

    all_nodes.sort(key=lambda n: n.score or 0, reverse=True)
    all_nodes = all_nodes[:limit]

    rag_nodes = []
    for n in all_nodes:
        meta = n.node.metadata or {}
        section_full_text = meta.get("section_content") or n.node.text
        breadcrumb = meta.get("breadcrumb") or []
        document_title = meta.get("document_title")
        if not document_title and isinstance(breadcrumb, list) and breadcrumb:
            document_title = str(breadcrumb[0])
        heading = meta.get("section_title")
        if not heading and isinstance(breadcrumb, list) and breadcrumb:
            heading = str(breadcrumb[-1])
        rag_nodes.append(
            RagNode(
                node_id=n.node.node_id,
                parent_id=meta.get("parent_id"),
                document_id=meta.get("document_id", ""),
                document_title=document_title or "",
                heading=heading or "",
                summary=meta.get("section_content", n.node.text[:200]),
                full_text=section_full_text,
                page_range=str(meta.get("page_number", "")),
                section_id=meta.get("section_id"),
                score=n.score or 0.0,
            )
        )

    return RagContext(nodes=rag_nodes, sections=None, confidence=None)
