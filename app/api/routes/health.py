from datetime import UTC, datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
import httpx

from app.core import http_errors
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document
from app.api.deps import get_auth_context, AuthContext
from app.services.system.health import build_health_payload
from app.services.auth.throttle import RequestThrottle

router = APIRouter(tags=["health"])
throttle = RequestThrottle()
logger = logging.getLogger(__name__)


def _fetch_documents(limit: int = 100) -> list[Document]:
    try:
        with SessionLocal() as session:
            return session.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
    except Exception as e:
        logger.warning("Failed to fetch documents: %s", e)
        return []


def _fetch_qdrant_nodes(document_id: str | None, limit: int = 30) -> list[dict[str, Any]]:
    if not document_id:
        return []

    body: dict[str, Any] = {
        "with_payload": True,
        "with_vector": False,
        "limit": limit,
        "filter": {
            "must": [
                {
                    "key": "document_id",
                    "match": {"value": document_id},
                }
            ]
        },
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {}) if isinstance(data, dict) else {}
            points = result.get("points", []) if isinstance(result, dict) else []
            if isinstance(points, list):
                return points
    except Exception as e:
        logger.warning("Failed to fetch Qdrant nodes: %s", e)

    return []


def _fetch_qdrant_node(document_id: str, node_id: str) -> dict[str, Any] | None:
    if not document_id or not node_id:
        return None

    body: dict[str, Any] = {
        "with_payload": True,
        "with_vector": False,
        "limit": 1,
        "filter": {
            "must": [
                {"key": "document_id", "match": {"value": document_id}},
                {"key": "node_id", "match": {"value": node_id}},
            ]
        },
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.qdrant_api_key:
        headers["api-key"] = settings.qdrant_api_key

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/scroll",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {}) if isinstance(data, dict) else {}
            points = result.get("points", []) if isinstance(result, dict) else []
            if isinstance(points, list) and points:
                return points[0]
    except Exception as e:
        logger.warning("Failed to fetch Qdrant node: %s", e)

    return None


def _build_snapshot(selected_document_id: str | None = None) -> dict[str, Any]:
    payload = build_health_payload()
    docs = _fetch_documents()
    active_docs = sum(1 for d in docs if d.deleted_at is None)
    latest_document_id = str(docs[0].id) if docs else None
    target_document_id = selected_document_id or latest_document_id

    return {
        "status": payload.get("status", "unknown"),
        "timestamp": datetime.now(UTC).isoformat(),
        "active_docs": active_docs,
        "total_docs": len(docs),
        "latest_document_id": latest_document_id or "",
        "target_document_id": target_document_id or "",
        "checks": payload.get("checks", {}),
    }


@router.get("/health")
async def healthcheck(request: Request):
    """Public health endpoint for load balancers and monitoring - no authentication required."""
    payload = build_health_payload()
    return {"status": payload.get("status", "unknown")}


@router.get("/health/data")
async def health_data(request: Request, _auth: AuthContext = Depends(get_auth_context)):
    """Detailed health data - authentication required."""
    if not throttle.allow(
        f"throttle:health:data:{_auth.user_id}",
        limit=settings.effective_rate_limit(60),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many health data requests")

    selected_document_id = request.query_params.get("document_id")
    return _build_snapshot(selected_document_id=selected_document_id)


@router.get("/health/nodes")
async def health_nodes(request: Request, _auth: AuthContext = Depends(get_auth_context)):
    """JSON-only: list Qdrant nodes for a document. Authentication required. HTML rendering moved to /view/nodes."""
    if not throttle.allow(
        f"throttle:health:nodes:{_auth.user_id}",
        limit=settings.effective_rate_limit(60),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many health node list requests")

    document_id = request.query_params.get("document_id") or ""
    points = _fetch_qdrant_nodes(document_id=document_id, limit=300)
    return {
        "document_id": document_id,
        "count": len(points),
        "points": points,
    }


@router.get("/health/node")
async def health_node(request: Request, _auth: AuthContext = Depends(get_auth_context)):
    """JSON-only: get a single Qdrant node. Authentication required. HTML rendering moved to /view/node."""
    if not throttle.allow(
        f"throttle:health:node:{_auth.user_id}",
        limit=settings.effective_rate_limit(60),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests("Too many health node detail requests")

    document_id = request.query_params.get("document_id") or ""
    node_id = request.query_params.get("node_id") or ""
    point = _fetch_qdrant_node(document_id=document_id, node_id=node_id)
    return {
        "document_id": document_id,
        "node_id": node_id,
        "found": point is not None,
        "point": point,
    }
