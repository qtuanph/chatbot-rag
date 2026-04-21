from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthContext, get_auth_context
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.memory import UserMemory
from app.services.chat.memory import UserMemoryService


router = APIRouter(tags=["memories"])
memory_service = UserMemoryService()
logger = logging.getLogger(__name__)


class MemoryInput(BaseModel):
    memory_type: str = "instruction"  # preference | correction | instruction | fact
    content: str


class MemoryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    is_active: bool | None = None


class MemoryResponse(BaseModel):
    id: str
    memory_type: str
    content: str
    is_active: bool
    created_at: str


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(auth: AuthContext = Depends(get_auth_context)) -> MemoryListResponse:
    """List all active memories for the current user."""
    with SessionLocal() as session:
        rows = (
            session.query(UserMemory)
            .filter(UserMemory.user_id == auth.user_id)
            .order_by(UserMemory.created_at.desc())
            .all()
        )

    items = [
        MemoryResponse(
            id=str(row.id),
            memory_type=row.memory_type,
            content=row.content,
            is_active=row.is_active,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    return MemoryListResponse(items=items)


@router.post("/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(
    data: MemoryInput,
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryResponse:
    """Create a new memory for the current user."""
    if not data.content or not data.content.strip():
        raise http_errors.bad_request("Memory content cannot be empty")

    if data.memory_type not in ("preference", "correction", "instruction", "fact"):
        raise http_errors.bad_request(
            "Invalid memory type. Must be: preference, correction, instruction, or fact"
        )

    if len(data.content) > 1000:
        raise http_errors.bad_request("Memory content too long (max 1000 characters)")

    with SessionLocal() as session:
        memory = UserMemory(
            user_id=auth.user_id,
            memory_type=data.memory_type,
            content=data.content.strip(),
        )
        session.add(memory)
        session.commit()
        session.refresh(memory)

        result = MemoryResponse(
            id=str(memory.id),
            memory_type=memory.memory_type,
            content=memory.content,
            is_active=memory.is_active,
            created_at=memory.created_at.isoformat(),
        )

    memory_service._invalidate_cache(auth.user_id)
    return result


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    auth: AuthContext = Depends(get_auth_context),
) -> MemoryResponse:
    """Update a memory (toggle active, edit content)."""
    with SessionLocal() as session:
        memory = session.get(UserMemory, memory_id)
        if memory is None or str(memory.user_id) != auth.user_id:
            raise http_errors.not_found("Memory not found")

        if data.content is not None:
            memory.content = data.content.strip()
        if data.memory_type is not None:
            memory.memory_type = data.memory_type
        if data.is_active is not None:
            memory.is_active = data.is_active
        session.commit()
        session.refresh(memory)

        result = MemoryResponse(
            id=str(memory.id),
            memory_type=memory.memory_type,
            content=memory.content,
            is_active=memory.is_active,
            created_at=memory.created_at.isoformat(),
        )

    memory_service._invalidate_cache(auth.user_id)
    return result


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a memory."""
    with SessionLocal() as session:
        memory = session.get(UserMemory, memory_id)
        if memory is None or str(memory.user_id) != auth.user_id:
            raise http_errors.not_found("Memory not found")
        session.delete(memory)
        session.commit()

    memory_service._invalidate_cache(auth.user_id)
