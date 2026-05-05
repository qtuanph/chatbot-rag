"""Tree service — hierarchical document exploration business logic."""

from __future__ import annotations

import logging
import re
from collections import Counter

from app.repositories.document_repository import DocumentRepository
from app.repositories.section_repository import SectionRepository

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_NODES = 1000
HARD_MAX_NODES = 10000
MAX_SEARCH_RESULTS = 20
PREVIEW_CONTEXT_CHARS = 50
PREVIEW_MATCH_CHARS = 150
MAX_PREVIEW_LENGTH = 200


class TreeService:
    """Business logic for hierarchical document tree exploration."""

    def __init__(self, doc_repo: DocumentRepository, section_repo: SectionRepository) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo

    async def verify_document_exists(self, document_id: str) -> dict:
        """Verify document exists, return doc dict or raise ValueError."""
        doc = await self.doc_repo.get_full_document(document_id)
        if not doc:
            raise ValueError("Document not found")
        return doc

    async def get_document_tree(self, *, document_id: str, offset: int = 0, limit: int = 20) -> dict:
        """Get hierarchical tree structure with pagination."""
        doc = await self.verify_document_exists(document_id)
        sections = await self.section_repo.get_sections_by_document(document_id)

        ordered_sections = sorted(sections, key=self._section_sort_key)
        total_nodes = len(ordered_sections)

        if total_nodes == 0:
            return {
                "document_id": document_id,
                "document_title": doc["file_name"],
                "total_nodes": 0,
                "max_depth": 0,
                "offset": 0,
                "limit": limit,
                "nodes": [],
            }

        child_counts = Counter(sec.get("parent_section_id") for sec in ordered_sections if sec.get("parent_section_id"))
        page_sections = ordered_sections[offset : offset + limit]

        nodes_list = []
        for section in page_sections:
            breadcrumb = section.get("breadcrumb") or []
            page_range = section.get("page_range")
            nodes_list.append(
                {
                    "node_id": section.get("section_id", ""),
                    "title": section.get("title", ""),
                    "level": section.get("level", 0),
                    "breadcrumb": " > ".join(str(b) for b in breadcrumb) if breadcrumb else section.get("title", ""),
                    "parent_id": section.get("parent_section_id"),
                    "child_count": int(child_counts.get(section.get("section_id"), 0)),
                    "text_length": len(section.get("content") or ""),
                    "page_number": page_range or "?",
                    "page_range": page_range,
                }
            )

        max_depth = max((int(sec.get("level") or 0) for sec in ordered_sections), default=0)

        return {
            "document_id": document_id,
            "document_title": doc["file_name"],
            "total_nodes": total_nodes,
            "max_depth": max_depth,
            "offset": offset,
            "limit": limit,
            "nodes": nodes_list,
        }

    async def get_node_details(self, *, document_id: str, node_id: str) -> dict:
        """Get full details of a single node."""
        await self.verify_document_exists(document_id)
        section = await self.section_repo.get_section_by_section_id(document_id, node_id)

        if not section:
            raise ValueError("Node not found")

        text = section.get("content") or ""
        breadcrumb = section.get("breadcrumb") or []

        return {
            "node_id": node_id,
            "title": section.get("title", ""),
            "level": section.get("level", 0),
            "breadcrumb": " > ".join(str(b) for b in breadcrumb),
            "text": text,
            "metadata": {
                "page_number": section.get("page_range", "?"),
                "page_range": section.get("page_range"),
                "node_type": section.get("section_type", "section"),
                "order": section.get("order_index", 0),
                "char_count": len(text),
                "token_count": len(text.split()),
            },
        }

    async def search_nodes(self, *, document_id: str, query: str, limit: int = MAX_SEARCH_RESULTS) -> dict:
        """Search nodes by title or content with context preview."""
        await self.verify_document_exists(document_id)
        sections = await self.section_repo.search_sections_by_document(document_id, query)

        query_lower = query.lower()
        results = []
        for section in sections[:limit]:
            text = section.get("content") or ""
            preview_source = text if text else section.get("title", "")
            preview = self._create_preview(preview_source, query_lower)
            results.append(
                {
                    "node_id": section.get("section_id", ""),
                    "title": section.get("title", ""),
                    "preview": preview,
                    "highlight": query,
                }
            )

        return {"results": results}

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _section_sort_key(section: dict) -> tuple:
        order_index = int(section.get("order_index") or 0)
        page_start = TreeService._parse_page_start(section.get("page_range"))
        section_id = str(section.get("section_id") or "")
        return (order_index if order_index >= 0 else 0, 0 if page_start is not None else 1, page_start or 0, section_id)

    @staticmethod
    def _parse_page_start(page_range: str | None) -> int | None:
        if not page_range:
            return None
        match = re.match(r"^\s*(\d+)", str(page_range))
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _create_preview(text: str, query_lower: str) -> str:
        text_lower = text.lower()
        match_pos = text_lower.find(query_lower)

        if match_pos >= 0:
            start = max(0, match_pos - PREVIEW_CONTEXT_CHARS)
            end = min(len(text), match_pos + PREVIEW_MATCH_CHARS)
            preview = text[start:end]
            if start > 0:
                preview = "..." + preview
            if end < len(text):
                preview = preview + "..."
            return preview

        return text[:MAX_PREVIEW_LENGTH]
