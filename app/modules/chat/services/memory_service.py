"""Memory service — user memory CRUD with cache invalidation."""

from __future__ import annotations

from app.modules.chat.repositories.memory_repository import MemoryRepository
from app.modules.chat.services.user_memory_service import UserMemoryService

VALID_MEMORY_TYPES = ("preference", "correction", "instruction", "fact")


class MemoryService:
    """Business logic for user memory management."""

    def __init__(self, repo: MemoryRepository, user_memory_service: UserMemoryService) -> None:
        self.repo = repo
        self._user_memory_service = user_memory_service

    async def list_memories(self, user_id: str) -> list[dict]:
        return await self.repo.list_by_user(user_id)

    async def create_memory(self, *, user_id: str, memory_type: str, content: str) -> dict:
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty")
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError("Invalid memory type. Must be: preference, correction, instruction, or fact")
        if len(content) > 1000:
            raise ValueError("Memory content too long (max 1000 characters)")

        result = await self.repo.create(user_id=user_id, memory_type=memory_type, content=content.strip())
        await self._user_memory_service.invalidate_cache(user_id)
        return result

    async def update_memory(
        self,
        *,
        memory_id: str,
        user_id: str,
        content: str | None = None,
        memory_type: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        existing = await self.repo.get_by_id(memory_id)
        if existing is None or existing["user_id"] != user_id:
            raise ValueError("Memory not found")

        result = await self.repo.update(memory_id, content=content, memory_type=memory_type, is_active=is_active)
        await self._user_memory_service.invalidate_cache(user_id)
        return result

    async def delete_memory(self, *, memory_id: str, user_id: str) -> None:
        existing = await self.repo.get_by_id(memory_id)
        if existing is None or existing["user_id"] != user_id:
            raise ValueError("Memory not found")

        await self.repo.delete(memory_id)
        await self._user_memory_service.invalidate_cache(user_id)
