"""
Tree API endpoints for hierarchical document exploration.

Provides hierarchical tree structure, node details, and search functionality.
"""

import logging
import re
from collections import Counter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import AuthContext, get_auth_context
from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.core import Document
from app.services.auth.throttle import RequestThrottle
from app.services.storage.document_store import SectionRepository


router = APIRouter(tags=["tree"])
logger = logging.getLogger(__name__)
throttle = RequestThrottle()

# Constants
DEFAULT_MAX_NODES = 1000
HARD_MAX_NODES = 10000
MAX_SEARCH_RESULTS = 20
PREVIEW_CONTEXT_CHARS = 50
PREVIEW_MATCH_CHARS = 150
MAX_PREVIEW_LENGTH = 200


def _validate_uuid(uuid_str: str, field_name: str = "ID") -> None:
    """Validate UUID format, raise HTTPException if invalid."""
    try:
        UUID(uuid_str)
    except ValueError:
        raise http_errors.bad_request(f"Invalid {field_name} format") from None


def _verify_document_exists(document_id: str) -> Document:
    """Verify document exists, return document object or raise HTTPException."""
    with SessionLocal() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise http_errors.not_found("Document not found")
        return doc

def _create_preview(text: str, query_lower: str) -> str:
    """Create a text preview around the matched query term."""
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


def _parse_page_start(page_range: str | None) -> int | None:
    """Extract the first page number from a page range string."""
    if not page_range:
        return None
    match = re.match(r"^\s*(\d+)", str(page_range))
    if not match:
        return None
    return int(match.group(1))


def _section_sort_key(section: dict) -> tuple[int, int, str]:
    """Sort sections by canonical order first, then page span as a tie-breaker."""
    order_index = int(section.get("order_index") or 0)
    page_start = _parse_page_start(section.get("page_range"))
    section_id = str(section.get("section_id") or "")
    return (order_index if order_index >= 0 else 0, 0 if page_start is not None else 1, page_start or 0, section_id)


@router.get("/tree/{document_id}")
async def get_document_tree(
    document_id: str,
    offset: int = 0,
    limit: int = 20,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get hierarchical tree structure for a document with pagination.

    Query params:
        offset: Starting index (default 0)
        limit: Number of nodes per page (default 20, max 100)

    Response format:
    {
        "document_id": "uuid",
        "document_title": "Document.pdf",
        "total_nodes": 189,
        "max_depth": 3,
        "offset": 0,
        "limit": 20,
        "nodes": [...]
    }
    """
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:list:{auth.user_id}",
        limit=settings.effective_rate_limit(60),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many tree requests")

    # Clamp limit
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    try:
        doc = _verify_document_exists(document_id)
        with SessionLocal() as session:
            section_repo = SectionRepository(session)
            sections = section_repo.get_sections_by_document(document_id)

        ordered_sections = sorted(sections, key=_section_sort_key)
        total_nodes = len(ordered_sections)

        if total_nodes == 0:
            return {
                "document_id": document_id,
                "document_title": doc.file_name,
                "total_nodes": 0,
                "max_depth": 0,
                "offset": 0,
                "limit": limit,
                "nodes": []
            }

        child_counts = Counter(
            sec.get("parent_section_id")
            for sec in ordered_sections
            if sec.get("parent_section_id")
        )

        page_sections = ordered_sections[offset:offset + limit]

        nodes_list = []
        for section in page_sections:
            breadcrumb = section.get("breadcrumb") or []
            page_range = section.get("page_range")
            nodes_list.append({
                "node_id": section.get("section_id", ""),
                "title": section.get("title", ""),
                "level": section.get("level", 0),
                "breadcrumb": " > ".join(str(b) for b in breadcrumb) if breadcrumb else section.get("title", ""),
                "parent_id": section.get("parent_section_id"),
                "child_count": int(child_counts.get(section.get("section_id"), 0)),
                "text_length": len(section.get("content") or ""),
                "page_number": page_range or "?",
                "page_range": page_range,
            })

        max_depth = max((int(sec.get("level") or 0) for sec in ordered_sections), default=0)

        return {
            "document_id": document_id,
            "document_title": doc.file_name,
            "total_nodes": total_nodes,
            "max_depth": max_depth,
            "offset": offset,
            "limit": limit,
            "nodes": nodes_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tree for {document_id}: {e}", exc_info=True)
        raise http_errors.internal_server_error("Failed to retrieve document tree") from None


@router.get("/tree/{document_id}/nodes/{node_id}")
async def get_node_details(
    document_id: str,
    node_id: str,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get full details of a single node.

    Returns header (title) + context (full text content).

    Response format:
    {
        "node_id": "uuid",
        "title": "Section 1.1",
        "level": 2,
        "breadcrumb": "Document > Chapter 1 > Section 1.1",
        "text": "Full context/text content...",
        "metadata": {
            "page_number": 5,
            "node_type": "section",
            "order": 1,
            "char_count": 2500,
            "token_count": 500
        }
    }
    """
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:detail:{auth.user_id}",
        limit=settings.effective_rate_limit(120),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many node detail requests")

    try:
        _verify_document_exists(document_id)
        with SessionLocal() as session:
            section_repo = SectionRepository(session)
            section = section_repo.get_section_by_section_id(document_id, node_id)

        if not section:
            raise http_errors.not_found("Node not found")

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
                "token_count": len(text.split())
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node {node_id} for {document_id}: {e}", exc_info=True)
        raise http_errors.internal_server_error("Failed to retrieve node details") from None


@router.get("/tree/{document_id}/search")
async def search_nodes(
    document_id: str,
    query: str = Query(..., min_length=1, max_length=500),
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Search nodes by title or content.

    Returns matching nodes with context preview.

    Response format:
    {
        "results": [
            {
                "node_id": "uuid",
                "title": "Matching Section",
                "preview": "...context around match...",
                "highlight": "matched text"
            }
        ]
    }
    """
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:search:{auth.user_id}",
        limit=settings.effective_rate_limit(60),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many tree search requests")

    try:
        _verify_document_exists(document_id)
        with SessionLocal() as session:
            section_repo = SectionRepository(session)
            sections = section_repo.search_sections_by_document(document_id, query)

        query_lower = query.lower()
        results = []

        for section in sections[:MAX_SEARCH_RESULTS]:
            text = section.get("content") or ""
            preview_source = text if text else section.get("title", "")
            preview = _create_preview(preview_source, query_lower)
            results.append({
                "node_id": section.get("section_id", ""),
                "title": section.get("title", ""),
                "preview": preview,
                "highlight": query,
            })

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching nodes in {document_id}: {e}", exc_info=True)
        raise http_errors.internal_server_error("Failed to search nodes") from None
