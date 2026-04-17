"""
Tree API endpoints for hierarchical document exploration.

Provides hierarchical tree structure, node details, and search functionality.
"""

import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import AuthContext, get_auth_context
from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.core import Document
from app.adapters.vector_stores import build_vector_store
from app.services.throttle import RequestThrottle


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


def _get_max_nodes_limit() -> int:
    """Get maximum nodes limit from config with safety cap."""
    max_nodes = int(os.getenv("MAX_TREE_NODES", str(DEFAULT_MAX_NODES)))
    return min(max_nodes, HARD_MAX_NODES)


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
        vector_store = build_vector_store()

        # First: get total count with a small scroll
        count_data = vector_store.scroll(
            filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            with_payload=False,
            with_vector=False,
            limit=10000,  # Qdrant scroll limit for counting
        )
        total_nodes = len(count_data)

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

        # Now get paginated nodes (offset + limit from the full set)
        all_nodes_data = vector_store.scroll(
            filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            with_payload=True,
            with_vector=False,
            limit=10000,
        )

        # Apply pagination
        paginated = all_nodes_data[offset:offset + limit]

        # Build node list
        nodes_list = []
        for point in paginated:
            payload = point.get("payload", {})
            node_id = payload.get("node_id", "")
            breadcrumb = payload.get("metadata", {}).get("breadcrumb", [])

            nodes_list.append({
                "node_id": node_id,
                "title": payload.get("section_title", ""),
                "level": payload.get("metadata", {}).get("level", 0),
                "breadcrumb": " > ".join(str(b) for b in breadcrumb) if breadcrumb else payload.get("section_title", ""),
                "parent_id": payload.get("parent_id"),
                "child_count": 0,
                "text_length": len(payload.get("text", "")),
                "page_number": payload.get("metadata", {}).get("page_number", "?"),
            })

        max_depth = max(
            (len(point.get("payload", {}).get("metadata", {}).get("breadcrumb", [])) for point in all_nodes_data),
            default=0,
        )

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
    _validate_uuid(node_id, "node ID")
    if not throttle.allow(
        f"throttle:tree:detail:{auth.user_id}",
        limit=settings.effective_rate_limit(120),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many node detail requests")

    try:
        _verify_document_exists(document_id)
        vector_store = build_vector_store()

        nodes_data = vector_store.scroll(
            filter={
                "must": [
                    {"key": "document_id", "match": {"value": document_id}},
                    {"key": "node_id", "match": {"value": node_id}}
                ]
            },
            with_payload=True,
            with_vector=False,
            limit=1
        )

        if not nodes_data:
            raise http_errors.not_found("Node not found")

        point = nodes_data[0]
        payload = point.get("payload", {})
        text = payload.get("text", "")
        metadata = payload.get("metadata", {})

        return {
            "node_id": node_id,
            "title": payload.get("section_title", ""),
            "level": metadata.get("level", 0),
            "breadcrumb": " > ".join(str(b) for b in metadata.get("breadcrumb", [])),
            "text": text,
            "metadata": {
                "page_number": metadata.get("page_number", "?"),
                "node_type": metadata.get("node_type", "unknown"),
                "order": metadata.get("order", 0),
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
        vector_store = build_vector_store()

        limit = _get_max_nodes_limit()
        nodes_data = vector_store.scroll(
            filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            with_payload=True,
            with_vector=False,
            limit=limit
        )

        query_lower = query.lower()
        results = []

        for point in nodes_data:
            payload = point.get("payload", {})
            title = payload.get("section_title", "")
            text = payload.get("text", "")
            node_id = payload.get("node_id", "")

            if query_lower in title.lower() or query_lower in text.lower():
                preview = _create_preview(text, query_lower)
                results.append({
                    "node_id": node_id,
                    "title": title,
                    "preview": preview,
                    "highlight": query
                })

        return {"results": results[:MAX_SEARCH_RESULTS]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching nodes in {document_id}: {e}", exc_info=True)
        raise http_errors.internal_server_error("Failed to search nodes") from None
