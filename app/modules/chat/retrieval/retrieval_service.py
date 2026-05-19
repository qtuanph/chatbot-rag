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
from app.modules.documents.utils import get_async_bm25_encoder
from app.utils.cache import QueryEmbeddingCache, SemanticCache

from app.models.rag import RagNode, RagSection, RagContext
from app.modules.documents.utils.document_registry import DocumentRegistry
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

        from app.modules.documents.repositories import DocumentRepository

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
        from app.modules.documents.repositories import DocumentRepository

        queries = [query] if isinstance(query, str) else query
        original_query = queries[0] if isinstance(query, str) else str(query)
        primary_query = queries[0]

        if not primary_query or len(primary_query.strip()) < 3:
            return RagContext(nodes=[])

        # Knowledge Graph enhancement (optional)
        if settings.kg_enabled:
            kg_contexts = await self._get_kg_context(primary_query)
            if kg_contexts:
                logger.info("[RAG-KG] Enhanced query with %d KG contexts", len(kg_contexts))

        _t0 = time.monotonic()

        latest_doc_ids = await self._latest_document_ids(session)
        if not latest_doc_ids:
            return RagContext(nodes=[])

        doc_ids = sorted(list(latest_doc_ids))

        doc_repo = DocumentRepository(session)
        title_by_id = await doc_repo.get_titles_by_ids(doc_ids)
        if not title_by_id:
            return RagContext(nodes=[])

        # ── Stage 1: Unified Multi-Intent Search ──────────────────────────────
        svc = self._get_embedding_service()
        vs = self._get_vector_store()
        bm25_encoder = await get_async_bm25_encoder(self.redis)

        async def _get_embedding(q_text: str):
            v = await self.query_cache.get(q_text)
            if v is None:
                embed_fn = getattr(svc, "embed_query", None) or svc.embed
                v = await embed_fn(q_text)
                await self.query_cache.set(q_text, v)
            return v

        query_vectors = await asyncio.gather(*[_get_embedding(q) for q in queries])

        # HyDE: generate hypothetical document and embed it for short-query enrichment
        hyde_vector = None
        if settings.retrieval_query_expansion_enabled and len(queries) <= 2 and len(original_query) < 100:
            try:
                from app.modules.chat.retrieval.hyde_service import hyde_generate

                hyde_text = await asyncio.wait_for(hyde_generate(original_query), timeout=1.5)
                if hyde_text:
                    hyde_vector = await _get_embedding(hyde_text)
                    if hyde_vector is not None:
                        logger.info("[RAG-HyDE] Added HyDE vector for: '%s'", original_query[:60])
            except asyncio.TimeoutError:
                logger.debug("[RAG-HyDE] Generation timed out, skipping.")
            except Exception as e:
                logger.debug("[RAG-HyDE] Failed: %s", e)

        if hyde_vector is not None:
            query_vectors.append(hyde_vector)

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
                top_n = settings.retrieval_rerank_top_k
                rerank_candidates = deduped_results[:top_n]
                # rerank() now returns the list of objects with updated scores
                reranked_docs = await reranker.rerank(
                    query=primary_query, documents=rerank_candidates, text_attr="text"
                )

                # Merge reranked results back into the main list
                # (Reranked list is sorted, items not reranked stay at the bottom)
                others = deduped_results[top_n:]
                deduped_results = reranked_docs + others
                logger.info("[PERF-RAG] Reranking complete: %d nodes", len(rerank_candidates))
            except Exception as e:
                logger.warning("Reranking failed: %s", e)

        # ── Stage 2.6: "Soi sáng" (Neighboring Node Expansion) ───────────────
        if settings.retrieval_context_expansion_window > 0 and deduped_results:
            deduped_results = await self._expand_neighbor_nodes(vs, deduped_results[:limit])

        # ── Confidence Scoring ────────────────────────────────────────────────
        from app.modules.chat.retrieval.confidence_scorer import RetrievalConfidence

        confidence = RetrievalConfidence.score(deduped_results[:limit])
        logger.info(
            "[RAG-CONFIDENCE] %s (max=%.3f, avg=%.3f)",
            confidence["status"],
            confidence["max_score"],
            confidence["avg_score"],
        )

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
            await self.semantic_cache.set(original_query, query_vectors[0], result_dict)

        return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None, confidence=confidence)

    async def _get_kg_context(self, query: str) -> list[str]:
        """Get context from Knowledge Graph for query enhancement."""
        try:
            from app.modules.documents.kg import get_knowledge_graph

            kg = get_knowledge_graph()
            results = await kg.query(query, top_k=3)
            return [r.get("entity", "") for r in results if r.get("entity")]
        except Exception as e:
            logger.warning("[KG] Failed to get context: %s", e)
            return []

    async def _expand_neighbor_nodes(
        self, vs: QdrantVectorStore, seed_results: list[RetrievedDocument]
    ) -> list[RetrievedDocument]:
        """
        Expand a set of seed nodes by fetching their neighbors (before/after).
        This provides a continuous context window for the LLM.
        """
        window = settings.retrieval_context_expansion_window
        if not window or not seed_results:
            return seed_results

        expanded_map: dict[str, RetrievedDocument] = {r.node_id: r for r in seed_results}

        # Identify documents and their order ranges
        # document_id -> (min_order, max_order)
        doc_ranges: dict[str, set[int]] = {}
        for r in seed_results:
            doc_id = r.document_id
            order = r.metadata.get("order", 0)
            if doc_id not in doc_ranges:
                doc_ranges[doc_id] = set()
            for o in range(max(0, order - window), order + window + 1):
                doc_ranges[doc_id].add(o)

        # Fetch neighbors in parallel per document
        async def fetch_doc_neighbors(doc_id: str, orders: set[int]) -> list[RetrievedDocument]:
            try:
                # Build Qdrant filter for the specific document and orders
                # Note: scroll doesn't support complex range+match well in one go,
                # but we can filter by document_id and then filter results in-memory
                # or use multiple scroll calls if needed.
                # Optimization: Fetch all points for this document within the min/max order range

                points, _ = await vs.scroll(
                    query_filter={"must": [{"key": "document_id", "match": {"value": doc_id}}]},  # Simple filter
                    limit=settings.retrieval_expansion_scroll_limit,  # Max nodes per doc in neighbor window
                    with_payload=True,
                )

                # Manual filter for order since our vs.scroll is simplified
                neighbors = []
                for p in points:
                    p_order = p["payload"].get("order") or p["payload"].get("metadata", {}).get("order", 0)
                    if p_order in orders:
                        neighbors.append(
                            RetrievedDocument(
                                node_id=str(p["payload"].get("node_id", p["id"])),
                                document_id=str(p["payload"].get("document_id", doc_id)),
                                text=str(p["payload"].get("text", "")),
                                score=0.0,  # Neighbors don't have search scores
                                metadata={
                                    "page_number": p["payload"].get("page_number"),
                                    "section_title": p["payload"].get("section_title"),
                                    "section_content": p["payload"].get("section_content", ""),
                                    "order": p_order,
                                    "breadcrumb": p["payload"].get("breadcrumb", []),
                                    "custom": p["payload"].get("metadata", {}),
                                },
                            )
                        )
                return neighbors
            except Exception as e:
                logger.error("Failed to fetch neighbors for doc %s: %s", doc_id, e)
                return []

        all_neighbors_nested = await asyncio.gather(*[fetch_doc_neighbors(did, o) for did, o in doc_ranges.items()])

        for neighbor_list in all_neighbors_nested:
            for n in neighbor_list:
                if n.node_id not in expanded_map:
                    expanded_map[n.node_id] = n

        # Final step: Sort by document and then order to ensure linear reading
        final_results = list(expanded_map.values())
        final_results.sort(key=lambda x: (x.document_id, x.metadata.get("order", 0)))

        logger.info("[RAG-EXPANSION] Expanded %d seeds into %d nodes", len(seed_results), len(final_results))
        return final_results
