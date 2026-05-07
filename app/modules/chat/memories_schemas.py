"""Pydantic schemas for memories API."""

from __future__ import annotations

from pydantic import BaseModel


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
