"""
Tree API endpoints for hierarchical document exploration.

Provides hierarchical tree structure, node details, and search functionality.
"""

import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import AuthContext, get_auth_context
from app.db.session import SessionLocal
from app.models.core import Document
from app.adapters.vector_stores import build_vector_store


router = APIRouter(tags=["tree"])
logger = logging.getLogger(__name__)

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
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format") from None


def _verify_document_exists(document_id: str) -> Document:
    """Verify document exists, return document object or raise HTTPException."""
    with SessionLocal() as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
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
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get hierarchical tree structure for a document.

    Returns complete tree with parent-child relationships.

    Response format:
    {
        "document_id": "uuid",
        "document_title": "Document.pdf",
        "total_nodes": 45,
        "max_depth": 3,
        "nodes": [
            {
                "node_id": "uuid",
                "title": "Chapter 1",
                "level": 1,
                "breadcrumb": "Document > Chapter 1",
                "parent_id": null,
                "child_count": 5,
                "text_length": 2500,
                "page_number": 1
            },
            ...
        ]
    }
    """
    _validate_uuid(document_id, "document ID")

    try:
        doc = _verify_document_exists(document_id)
        vector_store = build_vector_store()

        limit = _get_max_nodes_limit()
        nodes_data = vector_store.scroll(
            filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
            with_payload=True,
            with_vector=False,
            limit=limit
        )

        if not nodes_data:
            return {
                "document_id": document_id,
                "document_title": doc.file_name,
                "total_nodes": 0,
                "max_depth": 0,
                "nodes": []
            }

        # Build tree structure
        nodes_list = []
        node_map = {}

        for point in nodes_data:
            payload = point.get("payload", {})
            node_id = payload.get("node_id", "")
            breadcrumb = payload.get("metadata", {}).get("breadcrumb", [])

            node_map[node_id] = {
                "node_id": node_id,
                "title": payload.get("section_title", ""),
                "level": payload.get("metadata", {}).get("level", 0),
                "breadcrumb": " > ".join(str(b) for b in breadcrumb) if breadcrumb else payload.get("section_title", ""),
                "parent_id": payload.get("parent_id"),
                "child_count": 0,
                "text_length": len(payload.get("text", "")),
                "page_number": payload.get("metadata", {}).get("page_number", "?"),
            }
            nodes_list.append(node_map[node_id])

        # Calculate child counts
        for node in nodes_list:
            parent_id = node["parent_id"]
            if parent_id and parent_id in node_map:
                node_map[parent_id]["child_count"] += 1

        max_depth = max((n["level"] for n in nodes_list), default=0)

        return {
            "document_id": document_id,
            "document_title": doc.file_name,
            "total_nodes": len(nodes_list),
            "max_depth": max_depth,
            "nodes": nodes_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tree for {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve document tree") from None


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
            raise HTTPException(status_code=404, detail="Node not found")

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
        raise HTTPException(status_code=500, detail="Failed to retrieve node details") from None


@router.get("/tree/{document_id}/search")
async def search_nodes(
    document_id: str,
    query: str,
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
        raise HTTPException(status_code=500, detail="Failed to search nodes") from None
