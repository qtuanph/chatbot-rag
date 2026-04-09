from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import and_, func, or_, true
from sqlalchemy.orm import Session

from app.models.core import Document
from app.core.config import settings
from app.adapters.embeddings.bge_m3 import BGEM3Embedding
from app.adapters.vector_stores.qdrant import QdrantVectorStore


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
def _get_embedding_service() -> BGEM3Embedding:
    return BGEM3Embedding(
        model_name="BAAI/bge-m3",
        batch_size=settings.embedding_batch_size,
        normalize=settings.embedding_normalize,
    )


@lru_cache(maxsize=1)
def _get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        timeout=settings.qdrant_timeout,
    )


def retrieve_context(session: Session, query: str, limit: int = 5) -> RagContext:
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

    query_vector = _get_embedding_service().embed(query)
    retrieved = _get_vector_store().retrieve(
        query_vector=query_vector,
        top_k=max(limit, 1),
        document_ids_filter=list(title_by_id.keys()),
    )

    nodes: list[RagNode] = []
    for item in retrieved[:limit]:
        heading = item.metadata.get("section_title") or item.metadata.get("node_type") or "Section"
        page_number = item.metadata.get("page_number")
        page_range = str(page_number) if page_number else None
        nodes.append(
            RagNode(
                node_id=item.node_id,
                parent_id=item.metadata.get("parent_id"),
                document_id=item.document_id,
                document_title=title_by_id.get(item.document_id, "Untitled Document"),
                heading=str(heading),
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
            "answer": "Chưa có tài liệu nào được index để trả lời câu hỏi này.",
            "citations": [],
            "context": [],
        }

    intro = "Dựa trên tài liệu đã upload, mình tìm được các đoạn liên quan nhất:"
    bullets = []
    citations = []
    for idx, node in enumerate(context.nodes, start=1):
        excerpt = (node.summary or node.full_text[:280]).strip().replace("\n", " ")
        bullets.append(f"{idx}. {node.document_title} - {node.heading}: {excerpt}")
        citations.append({
            "document_id": node.document_id,
            "node_id": node.node_id,
            "title": node.document_title,
            "heading": node.heading,
            "page_range": node.page_range,
        })

    answer = f"{intro}\n" + "\n".join(bullets)
    return {"answer": answer, "citations": citations, "context": [node.__dict__ for node in context.nodes]}
