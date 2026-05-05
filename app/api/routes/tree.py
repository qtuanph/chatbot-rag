"""Tree API — hierarchical document exploration."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_context, get_tree_service
from app.core import http_errors
from app.core.config import settings
from app.utils.throttle import RequestThrottle
from app.services.documents.tree_service import TreeService

router = APIRouter(tags=["tree"])
throttle = RequestThrottle()


def _validate_uuid(uuid_str: str, field_name: str = "ID") -> None:
    try:
        UUID(uuid_str)
    except ValueError:
        raise http_errors.bad_request(f"Invalid {field_name} format") from None


@router.get("/tree/{document_id}")
async def get_document_tree(
    document_id: str,
    offset: int = 0,
    limit: int = 20,
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
):
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:list:{auth.user_id}", limit=settings.effective_rate_limit(60), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many tree requests")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    try:
        return await service.get_document_tree(document_id=document_id, offset=offset, limit=limit)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None


@router.get("/tree/{document_id}/nodes/{node_id}")
async def get_node_details(
    document_id: str,
    node_id: str,
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
):
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:detail:{auth.user_id}", limit=settings.effective_rate_limit(120), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many node detail requests")
    try:
        return await service.get_node_details(document_id=document_id, node_id=node_id)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None


@router.get("/tree/{document_id}/search")
async def search_nodes(
    document_id: str,
    query: str = Query(..., min_length=1, max_length=500),
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
):
    _validate_uuid(document_id, "document ID")
    if not throttle.allow(
        f"throttle:tree:search:{auth.user_id}", limit=settings.effective_rate_limit(60), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many tree search requests")
    try:
        return await service.search_nodes(document_id=document_id, query=query)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
