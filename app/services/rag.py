from __future__ import annotations

import logging
import re
from functools import lru_cache
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import and_, func, or_, true
from sqlalchemy.orm import Session

from app.models.core import Document
from app.core.config import settings
from app.adapters.base import BaseEmbedding
from app.adapters.embeddings import build_embedding_service
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.services.query_cache import QueryEmbeddingCache

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class RagContext:
    nodes: list[RagNode]


def _tokenize(query: str) -> list[str]:
    tokens = [token.lower() for token in re.findall(r"[A-Za-zÀ-ỹ0-9_]+", query)]
    stopwords = {"the", "and", "or", "la", "va", "cua", "cho", "voi", "theo", "to", "of", "a", "an", "is", "are"}
    return [token for token in tokens if len(token) > 1 and token not in stopwords][:12]


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
    latest_doc_ids = _latest_document_ids(session)
    if not latest_doc_ids:
        return RagContext(nodes=[])

    document_rows = (
        session.query(Document.id, Document.title)
        .filter(
            Document.deleted_at.is_(None),
            Document.status == "ready",
            Document.id.in_(latest_doc_ids),
        )
        .all()
    )
    title_by_id = {str(doc_id): title for doc_id, title in document_rows}

    # Query embedding — check cache first to avoid re-computing on repeated questions
    cache = _get_query_cache()
    query_vector = cache.get(query)
    if query_vector is None:
        svc = _get_embedding_service()
        # Use embed_query() to apply query_prefix (for E5-style models).
        # Falls back to embed() for adapters that don't override it.
        embed_fn = getattr(svc, "embed_query", None) or svc.embed
        query_vector = embed_fn(query)
        cache.set(query, query_vector)
        logger.debug("Query cache MISS — embedded locally")
    else:
        logger.debug("Query cache HIT — skipped embedding")


    retrieved = _get_vector_store().retrieve(
        query_vector=query_vector,
        top_k=50,   # Lấy nhiều context hơn để tổng hợp từ nhiều nguồn
        document_ids_filter=list(title_by_id.keys()),
    )

    # Drop low-relevance chunks — prevents LLM from being confused by noise
    min_score = settings.retrieval_min_score
    filtered = [item for item in retrieved if item.score >= min_score]
    if len(filtered) < len(retrieved):
        logger.debug(
            "Score filter: kept %d/%d chunks (threshold=%.2f)",
            len(filtered), len(retrieved), min_score,
        )

    nodes: list[RagNode] = []
    for item in filtered[:limit]:
        heading = item.metadata.get("section_title") or item.metadata.get("heading") or item.metadata.get("node_type") or "Nội dung"
        page_number = item.metadata.get("page_number")
        page_range = str(page_number) if page_number else None
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
            )
        )

    return RagContext(nodes=nodes)


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

    # Instructions for synthesis from multiple sources
    answer = (
        f"Câu hỏi: {query}\n\n"
        f"Tài liệu tham khảo ({len(context.nodes)} nguồn):\n{context_text}\n\n"
        f"Yêu cầu:\n"
        f"1. Đọc TẤT CẢ các nguồn trên\n"
        f"2. TỔNG HỢP thông tin từ nhiều nguồn nếu cần\n"
        f"3. Viết câu trả lời hoàn chỉnh, có phân tích\n"
        f"4. Dùng trích dẫn [1], [2], [3] khi cần thiết\n"
        f"5. Trả lời ngôn ngữ của người dùng"
    )

    return {"answer": answer, "citations": citations, "context": [node.__dict__ for node in context.nodes]}
