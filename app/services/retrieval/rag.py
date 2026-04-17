from __future__ import annotations

import logging
from functools import lru_cache
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.core import Document, DocumentSection
from app.core.config import settings
from app.adapters.base import BaseEmbedding
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.services.retrieval.cache import QueryEmbeddingCache

logger = logging.getLogger(__name__)


def _validate_uuid(uuid_str: str) -> bool:
    """Validate UUID string format."""
    try:
        UUID(uuid_str)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _validate_uuid_list(uuid_list: list[str] | set[str]) -> list[str]:
    """
    Filter and validate UUID strings from a list.
    Returns only valid UUIDs.
    """
    return [uid for uid in uuid_list if _validate_uuid(uid)]


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



@lru_cache(maxsize=1)
def _get_embedding_service() -> BaseEmbedding:
    return build_embedding_service()


@lru_cache(maxsize=1)
def _get_vector_store() -> QdrantVectorStore:
    embedding_service = _get_embedding_service()
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=embedding_service.get_dimension(),
        timeout=settings.qdrant_timeout,
    )


@lru_cache(maxsize=1)
def _get_query_cache() -> QueryEmbeddingCache:
    import redis
    client = redis.Redis.from_url(settings.redis_url, decode_responses=False)
    return QueryEmbeddingCache(client)


def retrieve_context(session: Session, query: str, limit: int = 15) -> RagContext:
    """
    2-stage retrieval: Sections (coarse) → Chunks (fine) within matched sections.

    Stage 1: Embed query → search Qdrant → group by section_id → pick top sections
    Stage 2: Re-search within top sections for fine-grained chunks
    Falls back to flat retrieval if no section data available.
    """
    """
    Retrieve relevant document context for a query.

    Performance optimizations:
    - Single DB query for document titles (avoid N+1)
    - Query embedding cache for repeated questions
    - Efficient score filtering
    - Early exit if no documents available
    """
    # Early exit if query is too short or empty
    if not query or len(query.strip()) < 3:
        logger.debug("Query too short, returning empty context")
        return RagContext(nodes=[])

    latest_doc_ids = _latest_document_ids(session)
    if not latest_doc_ids:
        logger.debug("No active documents found")
        return RagContext(nodes=[])

    # Single query to fetch all document titles (avoid N+1 problem)
    # Validate all UUIDs before using in SQL query to prevent SQL injection
    valid_doc_ids = _validate_uuid_list(list(latest_doc_ids))
    if not valid_doc_ids:
        logger.debug("No valid document IDs after validation")
        return RagContext(nodes=[])

    document_rows = (
        session.query(Document.id, Document.title)
        .filter(
            Document.deleted_at.is_(None),
            Document.status == "ready",
            Document.id.in_(valid_doc_ids),
        )
        .all()
    )
    title_by_id = {str(doc_id): title for doc_id, title in document_rows}

    if not title_by_id:
        logger.debug("No document titles found")
        return RagContext(nodes=[])

    # Query embedding — check cache first to avoid re-computing on repeated questions
    cache = _get_query_cache()
    query_vector = cache.get(query)
    if query_vector is None:
        svc = _get_embedding_service()
        embed_fn = getattr(svc, "embed_query", None) or svc.embed
        query_vector = embed_fn(query)
        cache.set(query, query_vector)
        logger.debug("Query cache MISS — embedded locally")
    else:
        logger.debug("Query cache HIT — skipped embedding")

    vs = _get_vector_store()

    # ── Stage 1: Coarse section retrieval ────────────────────────────────
    # Search with larger top_k to find relevant sections
    section_top_k = settings.retrieval_section_top_k
    section_min_score = settings.retrieval_section_min_score

    coarse_results = vs.retrieve(
        query_vector=query_vector,
        top_k=50,
        document_ids_filter=list(title_by_id.keys()),
    )

    # Group by section_id to find top sections
    section_scores: dict[str, float] = {}
    section_doc_map: dict[str, str] = {}
    for item in coarse_results:
        if item.score < section_min_score:
            continue
        sec_id = item.metadata.get("custom", {}).get("section_id")
        if sec_id:
            if sec_id not in section_scores or item.score > section_scores[sec_id]:
                section_scores[sec_id] = item.score
                section_doc_map[sec_id] = item.document_id

    # Pick top N sections
    top_sections_ids = sorted(section_scores, key=section_scores.get, reverse=True)[:section_top_k]

    # Load section details from PostgreSQL
    rag_sections: list[RagSection] = []
    if top_sections_ids:
        section_rows = (
            session.query(DocumentSection)
            .filter(
                DocumentSection.document_id.in_(valid_doc_ids),
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

    # ── Stage 2: Fine-grained chunk retrieval within sections ────────────
    # If we have sections, do a targeted search within them
    if top_sections_ids:
        chunk_results = vs.retrieve(
            query_vector=query_vector,
            top_k=settings.retrieval_chunk_top_k * section_top_k,
            document_ids_filter=list(title_by_id.keys()),
        )
    else:
        # No sections found — fall back to flat retrieval
        chunk_results = coarse_results

    # Drop low-relevance chunks
    min_score = settings.retrieval_min_score
    filtered = [item for item in chunk_results if item.score >= min_score]
    if len(filtered) < len(chunk_results):
        logger.debug(
            "Score filter: kept %d/%d chunks (threshold=%.2f)",
            len(filtered), len(chunk_results), min_score,
        )

    # If we have sections, prefer chunks within those sections
    if top_sections_ids and filtered:
        in_section = []
        out_section = []
        for item in filtered:
            sec_id = item.metadata.get("custom", {}).get("section_id")
            if sec_id in top_sections_ids:
                in_section.append(item)
            else:
                out_section.append(item)
        # Prioritize in-section chunks, then fill with out-of-section
        filtered = in_section + out_section

    nodes: list[RagNode] = []
    for item in filtered[:limit]:
        heading = item.metadata.get("section_title") or item.metadata.get("heading") or item.metadata.get("node_type") or "Nội dung"
        page_number = item.metadata.get("page_number")
        page_range = str(page_number) if page_number else None
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
        "Retrieved %d nodes from %d sections for query (limit=%d)",
        len(nodes), len(top_sections_ids), limit,
    )
    return RagContext(nodes=nodes, sections=rag_sections if rag_sections else None)


def _latest_document_ids(session: Session) -> set[str]:
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
    return {str(row[0]) for row in rows if row and row[0]}


def build_answer(query: str, context: RagContext, history: list[dict[str, str]] | None = None) -> dict:
    if not context.nodes:
        return {
            "answer": "Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống.",
            "citations": [],
            "context": [],
        }

    # Build rich context for LLM with inline citations
    context_blocks = []
    citations = []
    for idx, node in enumerate(context.nodes, start=1):
        # Use full text for LLM to synthesize from multiple sources
        full_text = node.full_text or ""
        context_blocks.append(f"[{idx}] {node.document_title} - {node.heading}:\n{full_text}")

        citations.append({
            "document_id": node.document_id,
            "node_id": node.node_id,
            "title": node.document_title,
            "heading": node.heading,
            "page_range": node.page_range,
            "index": idx,
        })

    context_text = "\n\n".join(context_blocks)

    # Simple format — the AI provider's _build_prompt already handles
    # instruction formatting. Just pass the query + context.
    answer = (
        f"Câu hỏi: {query}\n\n"
        f"Tài liệu tham khảo ({len(context.nodes)} nguồn):\n{context_text}"
    )

    return {"answer": answer, "citations": citations, "context": [node.__dict__ for node in context.nodes]}
