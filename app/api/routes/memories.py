"""Memories API — CRUD for user memories."""

from fastapi import APIRouter, Depends, status

from app.api.deps import AuthContext, get_auth_context, get_memory_service
from app.core import http_errors
from app.core.config import settings
from app.schemas.memories import MemoryInput, MemoryListResponse, MemoryResponse, MemoryUpdate
from app.utils.throttle import RequestThrottle
from app.services.chat.memory_service import MemoryService

router = APIRouter(tags=["memories"])
throttle = RequestThrottle()


def _to_response(row: dict) -> MemoryResponse:
    return MemoryResponse(
        id=row["id"],
        memory_type=row["memory_type"],
        content=row["content"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    auth: AuthContext = Depends(get_auth_context), service: MemoryService = Depends(get_memory_service)
) -> MemoryListResponse:
    rows = service.list_memories(auth.user_id)
    return MemoryListResponse(items=[_to_response(r) for r in rows])


@router.post("/memories", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryInput,
    auth: AuthContext = Depends(get_auth_context),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    if not throttle.allow(
        f"throttle:memory:create:{auth.user_id}", limit=settings.effective_rate_limit(20), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many memory creation requests")
    try:
        result = service.create_memory(user_id=auth.user_id, memory_type=data.memory_type, content=data.content)
    except ValueError as e:
        raise http_errors.bad_request(str(e)) from None
    return _to_response(result)


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    auth: AuthContext = Depends(get_auth_context),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    if not throttle.allow(
        f"throttle:memory:update:{auth.user_id}", limit=settings.effective_rate_limit(20), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many memory update requests")
    try:
        result = service.update_memory(
            memory_id=memory_id,
            user_id=auth.user_id,
            content=data.content,
            memory_type=data.memory_type,
            is_active=data.is_active,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        raise http_errors.bad_request(msg) from None
    return _to_response(result)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    auth: AuthContext = Depends(get_auth_context),
    service: MemoryService = Depends(get_memory_service),
) -> None:
    if not throttle.allow(
        f"throttle:memory:delete:{auth.user_id}", limit=settings.effective_rate_limit(20), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many memory delete requests")
    try:
        service.delete_memory(memory_id=memory_id, user_id=auth.user_id)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
