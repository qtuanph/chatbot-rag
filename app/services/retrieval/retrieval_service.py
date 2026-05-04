"""RAG retrieval service — 4-stage retrieval pipeline with hybrid search."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RagNode:
    node_id: str
    parent_id: str | None
    document_id: str
    document_title: str
    heading: str
    summary: str | None
    full_text: str
    page_range: str | None
    section_id: str | None = None
    score: float = 0.0


@dataclass(frozen=True)
class RagSection:
    section_id: str
    document_id: str
    title: str
    content: str
    level: int
    image_count: int
    table_count: int
    breadcrumb: tuple[str, ...]


@dataclass(frozen=True)
class RagContext:
    nodes: list[RagNode]
    sections: list[RagSection] | None = None


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
    import redis

    client = redis.Redis.from_url(settings.redis_url, decode_responses=False)
    return QueryEmbeddingCache(client, model_name=settings.embedding_hf_model)


# ── TTL-cached document IDs ──────────────────────────────────────────────

_doc_ids_cache: tuple[float, set[str]] | None = None
_doc_ids_lock = threading.Lock()
_DOC_IDS_TTL = settings.doc_ids_cache_ttl


def _latest_document_ids(session: Session) -> set[str]:
    """Return latest-version document IDs with a 60-second TTL cache. Uses DocumentRepository."""
    global _doc_ids_cache
    with _doc_ids_lock:
        if _doc_ids_cache is not None:
            cached_at, cached_ids = _doc_ids_cache
            if time.monotonic() - cached_at < _DOC_IDS_TTL:
                return cached_ids

    from app.repositories.document_repository import DocumentRepository

    repo = DocumentRepository(session)
    result = repo.get_latest_active_document_ids()
    with _doc_ids_lock:
        _doc_ids_cache = (time.monotonic(), result)
    logger.debug("Refreshed document ID cache: %d docs", len(result))
    return result


def invalidate_doc_ids_cache() -> None:
    """Clear the cached document IDs. Call after document upload/delete."""
    global _doc_ids_cache
    with _doc_ids_lock:
        _doc_ids_cache = None


# ── Main retrieval ───────────────────────────────────────────────────────


def retrieve_context(
    session: Session,
    query: str | list[str],
    limit: int = 15,
) -> RagContext:
    """Retrieve relevant document context for query/queries using 4-stage retrieval.

    Stages: Hybrid search → Section grouping → Dedup → Cross-encoder rerank.
    """
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.section_repository import SectionRepository

    queries = [query] if isinstance(query, str) else query
    primary_query = queries[0]

    if not primary_query or len(primary_query.strip()) < 3:
        logger.debug("Query too short, returning empty context")
        return RagContext(nodes=[])

    _t0 = time.monotonic()

    doc_repo = DocumentRepository(session)
    section_repo = SectionRepository(session)

    latest_doc_ids = _latest_document_ids(session)
    if not latest_doc_ids:
        logger.debug("No active documents found")
        return RagContext(nodes=[])

    doc_ids = list(latest_doc_ids)
    title_by_id = doc_repo.get_titles_by_ids(doc_ids)
    if not title_by_id:
        logger.debug("No document titles found")
        return RagContext(nodes=[])

    _t1 = time.monotonic()
    logger.info("[PERF-RAG] Doc IDs + titles: %.3fs", _t1 - _t0)

    cache = _get_query_cache()
    svc = _get_embedding_service()
    embed_fn = getattr(svc, "embed_query", None) or svc.embed

    vs = _get_vector_store()
    sparse_encoder = get_bm25_encoder()

    section_top_k = settings.retrieval_section_top_k
    section_min_score = settings.retrieval_section_min_score
    min_score = settings.retrieval_min_score
    fetch_k = min(80, max(50, section_top_k * settings.retrieval_chunk_top_k))

    merged: dict[str, tuple] = {}

    for q in queries:
        query_vector = cache.get(q)
        if query_vector is None:
            query_vector = embed_fn(q)
            cache.set(q, query_vector)

        sparse_vector = None
        if sparse_encoder.is_ready:
            sparse_vector = sparse_encoder.encode_sparse_vector(q)

        results = vs.retrieve(
            query_vector=query_vector,
            top_k=fetch_k,
            document_ids_filter=list(title_by_id.keys()),
            sparse_vector=sparse_vector,
        )

        for item in results:
            nid = item.node_id
            if nid not in merged or item.score > merged[nid][1]:
                merged[nid] = (item, item.score)

    _t2 = time.monotonic()
    logger.info(
        "[PERF-RAG] Multi-query search: %d queries, %d unique results in %.3fs",
        len(queries),
        len(merged),
        _t2 - _t1,
    )

    all_results = [item for item, _ in sorted(merged.values(), key=lambda x: x[1], reverse=True)]

    # ── Stage 1: Identify top sections ────────────────────────────────────
    section_scores: dict[str, float] = {}
    section_doc_map: dict[str, str] = {}
    for item in all_results:
        if item.score < section_min_score:
            continue
        sec_id = item.metadata.get("custom", {}).get("section_id")
        if sec_id:
            if sec_id not in section_scores or item.score > section_scores[sec_id]:
                section_scores[sec_id] = item.score
                section_doc_map[sec_id] = item.document_id

    top_sections_ids = sorted(section_scores, key=section_scores.get, reverse=True)[  # type: ignore[arg-type]
        :section_top_k
    ]

    # Load section details via repository
    rag_sections: list[RagSection] = []
    if top_sections_ids:
        pairs = [(section_doc_map[sid], sid) for sid in top_sections_ids if sid in section_doc_map]
        section_rows = section_repo.get_sections_for_rag(pairs)
        for row in section_rows:
            rag_sections.append(
                RagSection(
                    section_id=row["section_id"],
                    document_id=str(row["document_id"]),
                    title=row["title"],
                    content=row["content"] or "",
                    level=row["level"],
                    image_count=row["image_count"],
                    table_count=row["table_count"],
                    breadcrumb=tuple(row["breadcrumb"] or []),
                )
            )

    # ── Stage 2: Re-rank in-memory ────────────────────────────────────────
    filtered = [item for item in all_results if item.score >= min_score]
    if len(filtered) < len(all_results):
        logger.debug(
            "Score filter: kept %d/%d chunks (threshold=%.2f)",
            len(filtered),
            len(all_results),
            min_score,
        )

    if top_sections_ids and filtered:
        top_sections_set = set(top_sections_ids)
        in_section: list = []
        out_section: list = []
        for item in filtered:
            sec_id = item.metadata.get("custom", {}).get("section_id")
            if sec_id in top_sections_set:
                in_section.append(item)
            else:
                out_section.append(item)
        in_section.sort(key=lambda x: x.score, reverse=True)
        out_section.sort(key=lambda x: x.score, reverse=True)
        filtered = in_section + out_section

    if filtered:
        _seen_texts: dict[str, int] = {}
        deduped: list = []
        for item in filtered:
            text_sig = (item.text or "")[:100]
            if text_sig in _seen_texts:
                prev_idx = _seen_texts[text_sig]
                if item.score > deduped[prev_idx].score:
                    deduped[prev_idx] = item
            else:
                _seen_texts[text_sig] = len(deduped)
                deduped.append(item)
        if len(deduped) < len(filtered):
            logger.debug("Dedup: %d → %d chunks", len(filtered), len(deduped))
        filtered = deduped

    # ── Stage 3: Cross-encoder reranking (optional, off by default) ─────
    if filtered and settings.retrieval_rerank_enabled:
        rerank_top_k = settings.retrieval_rerank_top_k
        _MAX_RERANK_CANDIDATES = settings.retrieval_max_rerank_candidates
        if len(filtered) > _MAX_RERANK_CANDIDATES:
            logger.debug(
                "Reranker cap: %d → %d candidates",
                len(filtered),
                _MAX_RERANK_CANDIDATES,
            )
            filtered = filtered[:_MAX_RERANK_CANDIDATES]
        if len(filtered) > rerank_top_k:
            _t_rerank = time.monotonic()
            _pre_rerank_count = len(filtered)
            try:
                from app.adapters.reranker import get_reranker

                reranker = get_reranker()
                filtered = reranker.rerank(
                    query=primary_query,
                    documents=filtered,
                    text_attr="text",
                    top_k=rerank_top_k,
                )
            except (RuntimeError, ValueError) as e:
                logger.warning(
                    "Reranker failed (%s), using score-based ranking",
                    e,
                )
            _t_rerank_end = time.monotonic()
            logger.info(
                "[PERF-RAG] Reranker: %.3fs (%d → %d)",
                _t_rerank_end - _t_rerank,
                _pre_rerank_count,
                len(filtered),
            )

    nodes: list[RagNode] = []
    for item in filtered[:limit]:
        heading = (
            item.metadata.get("section_title")
            or item.metadata.get("heading")
            or item.metadata.get("node_type")
            or "Nội dung"
        )
        custom_metadata = item.metadata.get("custom", {}) or {}
        page_start = custom_metadata.get("page_start") or item.metadata.get("page_number")
        page_end = custom_metadata.get("page_end") or page_start
        page_range = _format_page_range(page_start, page_end)
        sec_id = item.metadata.get("custom", {}).get("section_id")
        nodes.append(
            RagNode(
                node_id=item.node_id,
                parent_id=item.metadata.get("parent_id"),
                document_id=item.document_id,
                document_title=title_by_id.get(item.document_id, "Tài liệu"),
                heading=str(heading).strip(),
                summary=(item.text[:280] if item.text else None),
                full_text=item.text,
                page_range=page_range,
                section_id=sec_id,
                score=item.score,
            )
        )

    logger.debug(
        "Retrieved %d nodes from %d sections (single-query, limit=%d)",
        len(nodes),
        len(top_sections_ids),
        limit,
    )
    return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None)


def build_answer(query: str, context: RagContext, history: list[dict[str, str]] | None = None) -> dict:
    """Build the answer seed from RAG context for AI provider.

    Strategy: retrieve at chunk level for precision, present at section level
    for completeness. Full section content is sent to the LLM instead of
    individual chunk text, so the LLM sees the complete context including
    all details (examples, steps, lists) that may span multiple chunks.
    """
    if not context.nodes:
        return {
            "answer": "Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống.",
            "citations": [],
            "context": [],
        }

    section_map: dict[str, RagSection] = {}
    if context.sections:
        for sec in context.sections:
            section_map[sec.section_id] = sec

    sorted_nodes = sorted(context.nodes, key=lambda n: n.score, reverse=True)

    context_blocks = []
    citations = []
    seen_sections: set[str] = set()
    citation_idx = 0

    for node in sorted_nodes:
        sec = section_map.get(node.section_id) if node.section_id else None

        # Prefer full section content over chunk text
        if sec and sec.content and sec.section_id not in seen_sections:
            seen_sections.add(sec.section_id)
            citation_idx += 1
            breadcrumb_path = " > ".join(sec.breadcrumb) if sec.breadcrumb else sec.title
            page_info = f" (trang {node.page_range})" if node.page_range else ""
            context_blocks.append(f"**{breadcrumb_path}** — {node.document_title}{page_info}\n{sec.content}")
            citations.append(
                {
                    "document_id": node.document_id,
                    "node_id": node.node_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "page_range": node.page_range,
                    "index": citation_idx,
                }
            )
        elif sec is None or not sec or not sec.content:
            # Fallback: section missing/empty or no section_id — use chunk text
            citation_idx += 1
            page_info = f" (trang {node.page_range})" if node.page_range else ""
            header = f"**{node.heading}** — {node.document_title}{page_info}"
            context_blocks.append(f"{header}\n{node.full_text or ''}")
            citations.append(
                {
                    "document_id": node.document_id,
                    "node_id": node.node_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "page_range": node.page_range,
                    "index": citation_idx,
                }
            )
        # else: section already seen (dedup) — skip

    context_text = "\n\n".join(context_blocks)

    answer = f"Câu hỏi: {query}\n\n" f"Tài liệu tham khảo:\n{context_text}"

    return {"answer": answer, "citations": citations, "context": [node.__dict__ for node in sorted_nodes]}
