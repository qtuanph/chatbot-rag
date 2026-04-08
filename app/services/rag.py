from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import and_, func, or_, true
from sqlalchemy.orm import Session

from app.models.core import DocNode, Document


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


def retrieve_context(session: Session, query: str, limit: int = 5) -> RagContext:
    tokens = _tokenize(query)
    latest_doc_ids = _latest_document_ids(session)
    latest_filter = Document.id.in_(latest_doc_ids) if latest_doc_ids else true()
    base_query = (
        session.query(DocNode, Document.title)
        .join(Document, DocNode.document_id == Document.id)
        .filter(Document.deleted_at.is_(None), DocNode.level > 0, latest_filter)
    )

    if tokens:
        lowered_heading = func.lower(DocNode.heading)
        lowered_summary = func.lower(func.coalesce(DocNode.summary, ""))
        lowered_text = func.lower(func.coalesce(DocNode.full_text, ""))
        filters = [or_(lowered_heading.contains(token), lowered_summary.contains(token), lowered_text.contains(token)) for token in tokens]
        base_query = base_query.filter(or_(*filters))

    candidates = base_query.order_by(DocNode.created_at.desc()).limit(80).all()
    scored: list[tuple[int, RagNode]] = []
    for node, title in candidates:
        text = f"{node.heading}\n{node.summary or ''}\n{node.full_text}".lower()
        if tokens:
            heading_text = (node.heading or "").lower()
            heading_score = sum(heading_text.count(token) for token in tokens) * 3
            summary_text = (node.summary or "").lower()
            summary_score = sum(summary_text.count(token) for token in tokens) * 2
            body_score = sum(text.count(token) for token in tokens)
            score = heading_score + summary_score + body_score
        else:
            score = 1
        if score <= 0:
            continue
        scored.append(
            (
                score,
                RagNode(
                    node_id=str(node.id),
                    parent_id=str(node.parent_id) if node.parent_id else None,
                    document_id=str(node.document_id),
                    document_title=title,
                    heading=node.heading,
                    summary=node.summary,
                    full_text=node.full_text,
                    page_range=node.page_range,
                ),
            )
        )

    if not scored:
        recent = (
            session.query(DocNode, Document.title)
            .join(Document, DocNode.document_id == Document.id)
            .filter(Document.deleted_at.is_(None), DocNode.level > 0, latest_filter)
            .order_by(DocNode.created_at.desc())
            .limit(limit)
            .all()
        )
        nodes = [
            RagNode(
                node_id=str(node.id),
                parent_id=str(node.parent_id) if node.parent_id else None,
                document_id=str(node.document_id),
                document_title=title,
                heading=node.heading,
                summary=node.summary,
                full_text=node.full_text,
                page_range=node.page_range,
            )
            for node, title in recent
        ]
        return RagContext(nodes=_with_parent_context(session, nodes))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_nodes = [node for _, node in scored[:limit]]
    return RagContext(nodes=_with_parent_context(session, top_nodes))


def _latest_document_ids(session: Session) -> set[str]:
    latest_versions = (
        session.query(
            Document.file_name.label("file_name"),
            func.max(Document.version).label("max_version"),
        )
        .filter(Document.deleted_at.is_(None))
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
        .filter(Document.deleted_at.is_(None))
        .all()
    )
    return {str(row[0]) for row in rows if row and row[0]}


def _with_parent_context(session: Session, nodes: list[RagNode]) -> list[RagNode]:
    if not nodes:
        return []

    parent_ids = {node.parent_id for node in nodes if node.parent_id}
    if not parent_ids:
        return nodes

    parent_rows = session.query(DocNode).filter(DocNode.id.in_(parent_ids)).all()
    parent_map = {str(row.id): row for row in parent_rows}

    enriched: list[RagNode] = []
    for node in nodes:
        parent = parent_map.get(node.parent_id or "")
        if parent and parent.heading and parent.heading != "Document":
            parent_prefix = f"[{parent.heading}]\n"
            full_text = f"{parent_prefix}{node.full_text}" if node.full_text else parent_prefix
            summary = node.summary or parent.heading
            enriched.append(
                RagNode(
                    node_id=node.node_id,
                    parent_id=node.parent_id,
                    document_id=node.document_id,
                    document_title=node.document_title,
                    heading=node.heading,
                    summary=summary,
                    full_text=full_text,
                    page_range=node.page_range,
                )
            )
        else:
            enriched.append(node)

    return enriched


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
