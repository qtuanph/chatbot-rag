"""RAG retrieval service — 4-stage retrieval pipeline with hybrid search."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import Any

from app.adapters.base import BaseEmbedding
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.config import settings
from app.utils.bm25_index import get_bm25_encoder
from app.utils.query_cache import QueryEmbeddingCache, RagResultCache
from app.utils.semantic_cache import SemanticCache

from app.models.rag import RagNode, RagSection, RagContext
from app.utils.document_registry import DocumentRegistry
from app.adapters.base import RetrievedDocument
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


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


class RetrievalService:
    """
    Class-based RAG retrieval service to ensure strict Dependency Injection.
    This prevents event loop conflicts by requiring a loop-safe redis_client.
    """

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client
        self.registry = DocumentRegistry(redis_client)
        self.query_cache = QueryEmbeddingCache(redis_client, model_name=settings.embedding_hf_model)
        self.rag_cache = RagResultCache(redis_client)
        self.semantic_cache = SemanticCache(vector_dim=settings.embedding_vector_size, client=redis_client)

    @lru_cache(maxsize=1)
    def _get_embedding_service(self) -> BaseEmbedding:
        return build_embedding_service()

    @lru_cache(maxsize=1)
    def _get_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            collection_name=settings.qdrant_collection,
            vector_size=settings.embedding_vector_size,
            timeout=settings.qdrant_timeout,
        )

    async def invalidate_doc_ids_cache(self) -> None:
        """Clear the active document IDs cache."""
        await self.registry.invalidate_active_ids_async()

    async def _latest_document_ids(self, session: AsyncSession) -> set[str]:
        """Return active document IDs from Redis with DB fallback."""
        cached = await self.registry.get_active_ids_async()
        if cached:
            return cached

        from app.modules.documents.repository import DocumentRepository

        ids = await DocumentRepository(session).get_latest_active_document_ids()
        if ids:
            await self.registry.set_active_ids_async(ids)
        return ids

    async def retrieve_context(
        self,
        session: AsyncSession,
        query: str | list[str],
        limit: int = 15,
        positive_point_ids: list[str] | None = None,
        negative_point_ids: list[str] | None = None,
    ) -> RagContext:
        """Retrieve relevant document context using 4-stage retrieval."""
        from app.modules.documents.repository import DocumentRepository

        queries = [query] if isinstance(query, str) else query
        original_query = queries[0] if isinstance(query, str) else str(query)
        primary_query = queries[0]

        if not primary_query or len(primary_query.strip()) < 3:
            return RagContext(nodes=[])

        _t0 = time.monotonic()

        latest_doc_ids = await self._latest_document_ids(session)
        if not latest_doc_ids:
            return RagContext(nodes=[])

        doc_ids = sorted(list(latest_doc_ids))

        # ── Stage 0: Cache Layers ──────────────────────────
        if isinstance(query, str):
            cached_result = await self.rag_cache.get(original_query, doc_ids)
            if cached_result:
                logger.info("[PERF-RAG] Exact Cache Hit: %s", original_query)
                return RagContext(
                    nodes=[RagNode(**n) for n in cached_result.get("nodes", [])],
                    sections=(
                        [RagSection(**s) for s in cached_result.get("sections", [])]
                        if cached_result.get("sections")
                        else None
                    ),
                )

        doc_repo = DocumentRepository(session)
        title_by_id = await doc_repo.get_titles_by_ids(doc_ids)
        if not title_by_id:
            return RagContext(nodes=[])

        # ── Stage 1: Unified Multi-Intent Search ──────────────────────────────
        svc = self._get_embedding_service()
        vs = self._get_vector_store()
        bm25_encoder = get_bm25_encoder(self.redis)

        async def _get_embedding(q_text: str):
            v = await self.query_cache.get(q_text)
            if v is None:
                embed_fn = getattr(svc, "embed_query", None) or svc.embed
                v = await embed_fn(q_text)
                await self.query_cache.set(q_text, v)
            return v

        query_vectors = await asyncio.gather(*[_get_embedding(q) for q in queries])

        # Semantic Match Cache
        if isinstance(query, str) and query_vectors:
            sem_cached = await self.semantic_cache.get(query_vectors[0])
            if sem_cached:
                logger.info("[PERF-RAG] Semantic Cache Hit: %s", original_query)
                return RagContext(
                    nodes=[RagNode(**n) for n in sem_cached.get("nodes", [])],
                    sections=(
                        [RagSection(**s) for s in sem_cached.get("sections", [])]
                        if sem_cached.get("sections")
                        else None
                    ),
                )

        sparse_vectors: list[Any] = []
        if bm25_encoder.is_ready:
            sparse_vectors = await asyncio.gather(
                *[asyncio.to_thread(bm25_encoder.encode_sparse_vector, q) for q in queries]
            )

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
        _seen_texts: dict[str, int] = {}
        deduped_results: list[RetrievedDocument] = []
        for item in all_results:
            if item.score < settings.retrieval_min_score:
                continue
            # Simple prefix-based dedup
            sig = (item.text or "").strip()[:150]
            if sig not in _seen_texts:
                _seen_texts[sig] = len(deduped_results)
                deduped_results.append(item)
            else:
                # Keep highest score if duplicates found
                idx = _seen_texts[sig]
                if item.score > deduped_results[idx].score:
                    deduped_results[idx] = item

        # ── Stage 2.5: Reranking (Stage 4 in original docs) ───────────────────
        if settings.retrieval_rerank_enabled and deduped_results:
            try:
                from app.adapters.reranker import get_reranker

                reranker = get_reranker()
                # Re-rank the actual document objects
                rerank_candidates = deduped_results[: settings.retrieval_rerank_top_n]
                # rerank() now returns the list of objects with updated scores
                reranked_docs = await reranker.rerank(
                    query=primary_query, documents=rerank_candidates, text_attr="text"
                )

                # Merge reranked results back into the main list
                # (Reranked list is sorted, items not reranked stay at the bottom)
                others = deduped_results[settings.retrieval_rerank_top_n :]
                deduped_results = reranked_docs + others
                logger.info("[PERF-RAG] Reranking complete: %d nodes", len(rerank_candidates))
            except Exception as e:
                logger.warning("Reranking failed: %s", e)

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
            heading = item.metadata.get("section_title") or custom_metadata.get("heading") or "Nội dung"

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

        # Cache result
        if isinstance(query, str) and nodes:
            import dataclasses

            result_dict = {
                "nodes": [dataclasses.asdict(n) for n in nodes],
                "sections": [dataclasses.asdict(s) for s in rag_sections] if rag_sections else None,
            }
            await asyncio.gather(
                self.rag_cache.set(original_query, doc_ids, result_dict),
                self.semantic_cache.set(original_query, query_vectors[0], result_dict),
                return_exceptions=True,
            )

        return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None)
