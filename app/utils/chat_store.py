"""
Chat Store: High-performance chat history management using Redis and MessagePack.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

import msgpack
import logging
from typing import Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatStore:
    """Manages chat history using Redis and binary MessagePack serialization."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for ChatStore")
        self.client = client

    def active_key(self, scope_id: str) -> str:
        return f"chat:active:{scope_id}"

    def history_key(self, scope_id: str, session_id: str) -> str:
        return f"chat:history:{scope_id}:{session_id}"

    # ── Async Methods ────────────────────────────────────────────────

    async def set_active_session(self, scope_id: str, session_id: str) -> None:
        await self.client.set(self.active_key(scope_id), session_id)

    async def get_active_session(self, scope_id: str) -> str | None:
        raw = await self.client.get(self.active_key(scope_id))
        return raw.decode() if isinstance(raw, bytes) else raw

    async def append_message(self, scope_id: str, session_id: str, role: str, content: str) -> None:
        """Append a message (Async)."""
        key = self.history_key(scope_id, session_id)
        packed = msgpack.packb({"role": role, "content": content})
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, packed)
            await pipe.ltrim(key, -settings.chat_history_limit, -1)
            await pipe.expire(key, settings.chat_history_redis_ttl)
            await pipe.execute()

    async def get_history(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        """Retrieve chat history (Async)."""
        key = self.history_key(scope_id, session_id)
        raw_list = await self.client.lrange(key, 0, -1)
        if not raw_list:
            return []
        return [msgpack.unpackb(raw) for raw in raw_list]

    async def history_exists(self, scope_id: str, session_id: str) -> bool:
        """Check if history exists in Redis (Async)."""
        return await self.client.exists(self.history_key(scope_id, session_id)) > 0

    async def hydrate_from_db(self, scope_id: str, session_id: str, messages: list[dict[str, str]]) -> None:
        """Hydrate Redis cache from DB messages (Async)."""
        if not messages:
            return
        key = self.history_key(scope_id, session_id)
        packed_list = [msgpack.packb({"role": m["role"], "content": m["content"]}) for m in messages]
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.delete(key)
            await pipe.rpush(key, *packed_list)
            await pipe.ltrim(key, -settings.chat_history_limit, -1)
            await pipe.expire(key, settings.chat_history_redis_ttl)
            await pipe.execute()

    # ── Sync Methods (For Workers) ──────────────────────────────────

    def set_active_session_sync(self, scope_id: str, session_id: str) -> None:
        self.client.set(self.active_key(scope_id), session_id)

    def get_active_session_sync(self, scope_id: str) -> str | None:
        raw = self.client.get(self.active_key(scope_id))
        return raw.decode() if isinstance(raw, bytes) else raw

    def append_message_sync(self, scope_id: str, session_id: str, role: str, content: str) -> None:
        """Append a message (Sync)."""
        key = self.history_key(scope_id, session_id)
        packed = msgpack.packb({"role": role, "content": content})
        pipe = self.client.pipeline(transaction=True)
        pipe.rpush(key, packed)
        pipe.ltrim(key, -settings.chat_history_limit, -1)
        pipe.expire(key, settings.chat_history_redis_ttl)
        pipe.execute()

    def get_history_sync(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        """Retrieve chat history (Sync)."""
        key = self.history_key(scope_id, session_id)
        raw_list = self.client.lrange(key, 0, -1)
        if not raw_list:
            return []
        return [msgpack.unpackb(raw) for raw in raw_list]

    def history_exists_sync(self, scope_id: str, session_id: str) -> bool:
        """Check if history exists in Redis (Sync)."""
        return self.client.exists(self.history_key(scope_id, session_id)) > 0

    def hydrate_from_db_sync(self, scope_id: str, session_id: str, messages: list[dict[str, str]]) -> None:
        """Hydrate Redis cache from DB messages (Sync)."""
        if not messages:
            return
        key = self.history_key(scope_id, session_id)
        packed_list = [msgpack.packb({"role": m["role"], "content": m["content"]}) for m in messages]
        pipe = self.client.pipeline(transaction=True)
        pipe.delete(key)
        pipe.rpush(key, *packed_list)
        pipe.ltrim(key, -settings.chat_history_limit, -1)
        pipe.expire(key, settings.chat_history_redis_ttl)
        pipe.execute()
