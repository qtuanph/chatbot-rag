"""RAG retrieval service — 4-stage retrieval pipeline with hybrid search."""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import TYPE_CHECKING

from app.adapters.base import BaseEmbedding
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.config import settings
from app.utils.bm25_index import get_bm25_encoder
from app.utils.query_cache import QueryEmbeddingCache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.models.rag import RagNode, RagSection, RagContext
from app.utils.document_registry import DocumentRegistry

logger = logging.getLogger(__name__)
registry = DocumentRegistry()


def _format_page_range(page_start: int | None, page_end: int | None) -> str | None:
    if page_start is None and page_end is None:
        return None
    if page_start is None:
        page_start = page_end
    if page_end is None:
        page_end = page_start
    if page_start == page_end:
        return str(page_start)
    return f"{page_start}-{page_end}"


# ── Singleton adapters (lru_cache ensures one instance) ──────────────────


@lru_cache(maxsize=1)
def _get_embedding_service() -> BaseEmbedding:
    return build_embedding_service()


@lru_cache(maxsize=1)
def _get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
        timeout=settings.qdrant_timeout,
    )


@lru_cache(maxsize=1)
def _get_query_cache() -> QueryEmbeddingCache:
    return QueryEmbeddingCache(_redis_client, model_name=settings.embedding_hf_model)


@lru_cache(maxsize=1)
def _get_rag_result_cache() -> RagResultCache:
    from app.utils.query_cache import RagResultCache
    return RagResultCache(_redis_client)


# ── Distributed Document ID Cache (Redis 8.x) ──────────────────────────


from sqlalchemy.ext.asyncio import AsyncSession


async def _latest_document_ids(session: AsyncSession) -> set[str]:
    """Return active document IDs from Redis with DB fallback."""
    cached = await registry.get_active_ids_async()
    if cached:
        return cached

    from app.repositories.document_repository import DocumentRepository

    ids = await DocumentRepository(session).get_latest_active_document_ids()
    if ids:
        await registry.set_active_ids_async(ids)
    return ids


def invalidate_doc_ids_cache() -> None:
    registry.invalidate_active_ids()


# ── Main retrieval ───────────────────────────────────────────────────────


async def retrieve_context(
    session: AsyncSession,
    query: str | list[str],
    limit: int = 15,
    positive_point_ids: list[str] | None = None,
    negative_point_ids: list[str] | None = None,
) -> RagContext:
    """Retrieve relevant document context for query/queries using 4-stage retrieval.

    Stages: Result Cache → Hybrid search → Section grouping → Dedup → Assembly.
    """
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.section_repository import SectionRepository

    queries = [query] if isinstance(query, str) else query
    primary_query = queries[0]

    if not primary_query or len(primary_query.strip()) < 3:
        logger.debug("Query too short, returning empty context")
        return RagContext(nodes=[])

    _t0 = time.monotonic()

    latest_doc_ids = await _latest_document_ids(session)
    if not latest_doc_ids:
        logger.debug("No active documents found")
        return RagContext(nodes=[])

    doc_ids = sorted(list(latest_doc_ids))
    
    # ── Stage 0: Search Result Cache ──────────────────────────────────────
    rag_cache = _get_rag_result_cache()
    if isinstance(query, str):
        cached_result = await rag_cache.get(query, doc_ids)
        if cached_result:
            logger.info("[PERF-RAG] Search Result Cache Hit: %s", query)
            # Reconstruct RagContext from dict
            return RagContext(
                nodes=[RagNode(**n) for n in cached_result.get("nodes", [])],
                sections=[RagSection(**s) for s in cached_result.get("sections", [])] if cached_result.get("sections") else None
            )

    doc_repo = DocumentRepository(session)
    title_by_id = await doc_repo.get_titles_by_ids(doc_ids)
    if not title_by_id:
        logger.debug("No document titles found")
        return RagContext(nodes=[])

    # ── Stage 1: Unified Multi-Intent Search ──────────────────────────────
    cache = _get_query_cache()
    svc = _get_embedding_service()
    vs = _get_vector_store()
    sparse_encoder = get_bm25_encoder()

    import asyncio
    
    async def _get_embedding(q_text: str):
        v = await cache.get(q_text)
        if v is None:
            # Embedding models are usually thread-safe or process-safe but CPU-bound
            # We wrap them to keep the loop moving
            from fastapi.concurrency import run_in_threadpool
            embed_fn = getattr(svc, "embed_query", None) or svc.embed
            v = await run_in_threadpool(embed_fn, q_text)
            await cache.set(q_text, v)
        return v

    # Embed all queries in parallel
    query_vectors = await asyncio.gather(*[_get_embedding(q) for q in queries])
    
    sparse_vectors: list[Any] = []
    if sparse_encoder.is_ready:
        sparse_vectors = [sparse_encoder.encode_sparse_vector(q) for q in queries]

    # Single Unified call to Qdrant (Fusion + Hybrid + Filtering)
    fetch_k = settings.retrieval_chunk_top_k * 3
    all_results = await vs.retrieve(
        query_vectors=query_vectors,
        top_k=fetch_k,
        document_ids_filter=list(title_by_id.keys()),
        sparse_vectors=sparse_vectors,
        positive_point_ids=positive_point_ids,
        negative_point_ids=negative_point_ids,
    )

    _t1 = time.monotonic()
    logger.info("[PERF-RAG] Unified Async Retrieval: %.3fs", _t1 - _t0)

    # ── Stage 2: Deduplication & Context Assembly ─────────────────────────
    # Dedup by text signature to avoid near-duplicate chunks from expansion
    _seen_texts: dict[str, int] = {}
    deduped_results: list[RetrievedDocument] = []
    for item in all_results:
        if item.score < settings.retrieval_min_score:
            continue
        # Use first 150 chars as signature
        sig = (item.text or "").strip()[:150]
        if sig not in _seen_texts:
            _seen_texts[sig] = len(deduped_results)
            deduped_results.append(item)
    
    logger.debug("[RAG] Deduped %d -> %d chunks", len(all_results), len(deduped_results))

    # Assemble sections from enriched payload (No DB calls!)
    rag_sections: list[RagSection] = []
    seen_sec_ids: set[str] = set()
    
    for item in deduped_results:
        sec_id = item.metadata.get("custom", {}).get("section_id")
        if sec_id and sec_id not in seen_sec_ids:
            seen_sec_ids.add(sec_id)
            rag_sections.append(
                RagSection(
                    section_id=sec_id,
                    document_id=item.document_id,
                    title=item.metadata.get("section_title") or "Chương",
                    content=item.metadata.get("section_content") or "",
                    level=int(item.metadata.get("custom", {}).get("level", 0)),
                    image_count=int(item.metadata.get("custom", {}).get("image_count", 0)),
                    table_count=int(item.metadata.get("custom", {}).get("table_count", 0)),
                    breadcrumb=tuple(item.metadata.get("breadcrumb") or []),
                )
            )
        if len(rag_sections) >= settings.retrieval_section_top_k:
            break

    # ── Stage 3: Build RagNodes ───────────────────────────────────────────
    nodes: list[RagNode] = []
    for item in deduped_results[:limit]:
        custom_metadata = item.metadata.get("custom", {}) or {}
        page_start = custom_metadata.get("page_start") or item.metadata.get("page_number")
        page_end = custom_metadata.get("page_end") or page_start
        page_range = _format_page_range(page_start, page_end)
        
        heading = (
            item.metadata.get("section_title")
            or custom_metadata.get("heading")
            or "Nội dung"
        )
        
        nodes.append(
            RagNode(
                node_id=item.node_id,
                parent_id=item.metadata.get("parent_id"),
                document_id=item.document_id,
                document_title=title_by_id.get(item.document_id, "Tài liệu"),
                heading=str(heading).strip(),
                summary=None,
                full_text=item.text or "",
                page_range=page_range,
                section_id=custom_metadata.get("section_id"),
                score=item.score,
            )
        )

    # Cache result if it's a single string query
    if isinstance(query, str) and nodes:
        # Convert to dict for JSON serialization in Redis
        result_dict = {
            "nodes": [n.to_dict() if hasattr(n, "to_dict") else n.__dict__ for n in nodes],
            "sections": [s.to_dict() if hasattr(s, "to_dict") else s.__dict__ for s in rag_sections] if rag_sections else None
        }
        await rag_cache.set(query, doc_ids, result_dict)

    return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None)
