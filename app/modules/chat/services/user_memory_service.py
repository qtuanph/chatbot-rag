from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from app.core.config import settings

if TYPE_CHECKING:
    from app.modules.chat.repositories import MemoryRepository

logger = logging.getLogger(__name__)

_MEMORY_CACHE_TTL = settings.memory_cache_ttl
VALID_MEMORY_TYPES = {"preference", "correction", "instruction", "fact"}
MAX_MEMORY_CONTENT = 500


class UserMemoryService:
    """Manages persistent user memories with Redis Hash caching."""

    def __init__(self, redis_client: Any, memory_repo: MemoryRepository) -> None:
        self._redis = redis_client
        self._memory_repo = memory_repo

    def _cache_key(self, user_id: str) -> str:
        return f"user_memories:v2:{user_id}"

    async def get_active_memories(self, user_id: str) -> list[dict[str, str]]:
        """Retrieve memories from RedisJSON or DB fallback."""
        cache_key = self._cache_key(user_id)
        memories = await self._redis.json().get(cache_key)
        if memories:
            return memories

        rows = await self._memory_repo.list_active_by_user(user_id)
        memories = [{"type": r["memory_type"], "content": r["content"], "id": str(r["id"])} for r in rows]

        if memories:
            await self._redis.json().set(cache_key, "$", memories)
            await self._redis.expire(cache_key, _MEMORY_CACHE_TTL)

        return memories

    async def format_memories_for_prompt(self, user_id: str) -> str:
        memories = await self.get_active_memories(user_id)
        if not memories:
            return ""
        map_type = {"preference": "Sở thích", "correction": "Sửa đổi", "instruction": "Chỉ dẫn", "fact": "Thông tin"}
        lines = [f"- [{map_type.get(m['type'], 'Ghi nhớ')}] {m['content']}" for m in memories]
        return "THÔNG TIN ĐÃ GHI NHỚ VỀ NGƯỜI DÙNG:\n" + "\n".join(lines)

    async def add_memory(self, user_id: str, memory_type: str, content: str) -> None:
        """Add memory to DB and append to RedisJSON array. Deduplicates by content similarity."""
        existing = await self.get_active_memories(user_id)
        content_lower = content.lower().strip()
        for ex in existing:
            if ex["content"].lower().strip() == content_lower:
                logger.debug("Memory duplicate skipped: %s", content[:50])
                return

        m = await self._memory_repo.create(user_id=user_id, memory_type=memory_type, content=content)
        cache_key = self._cache_key(user_id)
        msg = {"type": memory_type, "content": content, "id": str(m["id"])}
        if not await self._redis.exists(cache_key):
            await self._redis.json().set(cache_key, "$", [msg])
            await self._redis.expire(cache_key, _MEMORY_CACHE_TTL)
        else:
            await self._redis.json().arrappend(cache_key, "$", msg)

    async def invalidate_cache(self, user_id: str) -> None:
        await self._redis.delete(self._cache_key(user_id))
