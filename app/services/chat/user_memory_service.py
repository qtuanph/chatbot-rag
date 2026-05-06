from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any
from app.core.config import settings

if TYPE_CHECKING:
    from app.adapters.ai.base import AIProvider
    from app.repositories.memory_repository import MemoryRepository

logger = logging.getLogger(__name__)

_MEMORY_CACHE_TTL = settings.memory_cache_ttl


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
        """Add memory to DB and append to RedisJSON array."""
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

    def should_extract_memory(self, user_message: str) -> bool:
        if not user_message:
            return False

        explicit_patterns = [r"nhớ", r"remember", r"ghi nhớ", r"lưu ý"]
        correction_patterns = [r"sai", r"không đúng", r"đừng", r"muốn", r"cần", r"nên"]

        msg_lower = user_message.lower()
        for pattern in explicit_patterns + correction_patterns:
            if re.search(pattern, msg_lower):
                return True
        return False

    async def extract_memories_from_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        ai_provider: AIProvider,
    ) -> None:
        """Extract memorable facts using Gemini."""
        if not self.should_extract_memory(user_message):
            return

        try:
            extraction_prompt = (
                "Trích xuất sở thích, sửa đổi, chỉ dẫn hoặc thông tin cá nhân từ tin nhắn người dùng.\n\n"
                f"Tin nhắn: {user_message}\n\n"
                "Trả về JSON array: "
                '[{"type": "preference|correction|instruction|fact", "content": "..."}]'
            )

            result = await ai_provider.chat([{"role": "user", "content": extraction_prompt}], context=[], citations=[])
            text = result.get("answer", "")
            if not text:
                return

            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                memories = json.loads(text[json_start:json_end])
                for m in memories:
                    if isinstance(m, dict) and m.get("content") and m.get("type"):
                        await self.add_memory(user_id, str(m["type"]), str(m["content"]))

        except Exception as e:
            logger.warning("Memory extraction failed: %s", e)
