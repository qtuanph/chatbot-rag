from __future__ import annotations

import logging
import time
from functools import lru_cache
from dataclasses import dataclass

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.core import Document, DocumentSection
from app.core.config import settings
from app.adapters.base import BaseEmbedding
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.services.retrieval.cache import QueryEmbeddingCache

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
# Avoids running a complex PostgreSQL subquery on every chat request.
# Cache is invalidated explicitly on document upload/delete.

_doc_ids_cache: tuple[float, set[str]] | None = None
_DOC_IDS_TTL = 60.0  # seconds


def _latest_document_ids(session: Session) -> set[str]:
    """Return latest-version document IDs with a 60-second TTL cache."""
    global _doc_ids_cache
    if _doc_ids_cache is not None:
        cached_at, cached_ids = _doc_ids_cache
        if time.monotonic() - cached_at < _DOC_IDS_TTL:
            return cached_ids

    latest_versions = (
        session.query(
            Document.file_name.label("file_name"),
            func.max(Document.version).label("max_version"),
        )
        .filter(Document.deleted_at.is_(None), Document.status == "ready")
        .group_by(Document.file_name)
        .subquery()
    )
    rows = (
        session.query(Document.id)
        .join(
            latest_versions,
            and_(
                Document.file_name == latest_versions.c.file_name,
                Document.version == latest_versions.c.max_version,
            ),
        )
        .filter(Document.deleted_at.is_(None), Document.status == "ready")
        .all()
    )
    result = {str(row[0]) for row in rows if row and row[0]}
    _doc_ids_cache = (time.monotonic(), result)  # type: ignore[assignment]
    logger.debug("Refreshed document ID cache: %d docs", len(result))
    return result


def invalidate_doc_ids_cache() -> None:
    """Clear the cached document IDs. Call after document upload/delete."""
    global _doc_ids_cache
    _doc_ids_cache = None


# ── Main retrieval ───────────────────────────────────────────────────────

def retrieve_context(session: Session, query: str, limit: int = 15) -> RagContext:
    """Retrieve relevant document context for a query using optimised 2-stage retrieval."""
    if not query or len(query.strip()) < 3:
        logger.debug("Query too short, returning empty context")
        return RagContext(nodes=[])

    _t0 = time.monotonic()

    latest_doc_ids = _latest_document_ids(session)
    if not latest_doc_ids:
        logger.debug("No active documents found")
        return RagContext(nodes=[])

    doc_ids = list(latest_doc_ids)

    # Fetch all document titles in one query (avoid N+1).
    document_rows = (
        session.query(Document.id, Document.title)
        .filter(
            Document.deleted_at.is_(None),
            Document.status == "ready",
            Document.id.in_(doc_ids),
        )
        .all()
    )
    title_by_id = {str(doc_id): title for doc_id, title in document_rows}
    if not title_by_id:
        logger.debug("No document titles found")
        return RagContext(nodes=[])

    _t1 = time.monotonic()
    logger.info("[PERF-RAG] Doc IDs + titles: %.3fs", _t1 - _t0)

    # Query embedding — Redis cache avoids re-computing on repeated questions.
    cache = _get_query_cache()
    query_vector = cache.get(query)
    if query_vector is None:
        svc = _get_embedding_service()
        embed_fn = getattr(svc, "embed_query", None) or svc.embed
        query_vector = embed_fn(query)
        cache.set(query, query_vector)
        _t2 = time.monotonic()
        logger.info("[PERF-RAG] Embed query (CACHE MISS): %.3fs", _t2 - _t1)
    else:
        _t2 = time.monotonic()
        logger.info("[PERF-RAG] Embed query (CACHE HIT): %.3fs", _t2 - _t1)

    vs = _get_vector_store()

    # ── Single Qdrant query (replaces 2 round-trips) ────────────────────
    section_top_k = settings.retrieval_section_top_k
    section_min_score = settings.retrieval_section_min_score
    min_score = settings.retrieval_min_score

    # Fetch enough results to cover both section discovery and chunk ranking.
    # One query instead of the old two-query approach.
    fetch_k = min(80, max(50, section_top_k * settings.retrieval_chunk_top_k))

    all_results = vs.retrieve(
        query_vector=query_vector,
        top_k=fetch_k,
        document_ids_filter=list(title_by_id.keys()),
    )

    _t3 = time.monotonic()
    logger.info("[PERF-RAG] Qdrant search: %.3fs (%d results)", _t3 - _t2, len(all_results))

    # ── Stage 1: Identify top sections from the single result set ────────
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

    top_sections_ids = sorted(
        section_scores, key=section_scores.get, reverse=True  # type: ignore[arg-type]
    )[:section_top_k]

    # Load section details from PostgreSQL.
    rag_sections: list[RagSection] = []
    if top_sections_ids:
        section_rows = (
            session.query(DocumentSection)
            .filter(
                DocumentSection.document_id.in_(doc_ids),
                DocumentSection.section_id.in_(top_sections_ids),
            )
            .all()
        )
        for row in section_rows:
            rag_sections.append(
                RagSection(
                    section_id=row.section_id,
                    document_id=str(row.document_id),
                    title=row.title,
                    content=row.content or "",
                    level=row.level,
                    image_count=row.image_count,
                    table_count=row.table_count,
                    breadcrumb=tuple(row.breadcrumb or []),
                )
            )

    # ── Stage 2: Re-rank in-memory (no 2nd Qdrant query) ────────────────
    # Drop low-relevance chunks first.
    filtered = [item for item in all_results if item.score >= min_score]
    if len(filtered) < len(all_results):
        logger.debug(
            "Score filter: kept %d/%d chunks (threshold=%.2f)",
            len(filtered), len(all_results), min_score,
        )

    # Prioritise chunks that belong to top sections.
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
        filtered = in_section + out_section

    # Build output nodes.
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
            )
        )

    logger.debug(
        "Retrieved %d nodes from %d sections (single-query, limit=%d)",
        len(nodes), len(top_sections_ids), limit,
    )
    return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None)


def build_answer(query: str, context: RagContext, history: list[dict[str, str]] | None = None) -> dict:
    if not context.nodes:
        return {
            "answer": "Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống.",
            "citations": [],
            "context": [],
        }

    # Build clean context blocks for LLM (no inline citation numbers).
    context_blocks = []
    citations = []
    for idx, node in enumerate(context.nodes, start=1):
        full_text = node.full_text or ""
        context_blocks.append(f"--- Tài liệu: {node.document_title} — {node.heading} ---\n{full_text}")

        citations.append({
            "document_id": node.document_id,
            "node_id": node.node_id,
            "title": node.document_title,
            "heading": node.heading,
            "page_range": node.page_range,
            "index": idx,
        })

    context_text = "\n\n".join(context_blocks)

    answer = (
        f"Câu hỏi: {query}\n\n"
        f"Tài liệu tham khảo:\n{context_text}"
    )

    return {"answer": answer, "citations": citations, "context": [node.__dict__ for node in context.nodes]}
