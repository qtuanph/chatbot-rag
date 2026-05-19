"""Data models for RAG retrieval."""

from __future__ import annotations
from dataclasses import dataclass


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
    confidence: dict | None = None  # From RetrievalConfidence.score()
