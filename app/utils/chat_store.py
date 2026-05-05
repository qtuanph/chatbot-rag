"""
Chat Store: High-performance chat history management using Redis and MessagePack.
Optimized for 200+ CCU with sub-millisecond serialization.
"""

import msgpack
import logging
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatStore:
    """Manages chat history using Redis and binary MessagePack serialization."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    def active_key(self, scope_id: str) -> str:
        return f"chat:active:{scope_id}"

    def history_key(self, scope_id: str, session_id: str) -> str:
        return f"chat:history:{scope_id}:{session_id}"

    async def set_active_session(self, scope_id: str, session_id: str) -> None:
        await self.client.set(self.active_key(scope_id), session_id)

    async def get_active_session(self, scope_id: str) -> str | None:
        return await self.client.get(self.active_key(scope_id))

    async def append_message(self, scope_id: str, session_id: str, role: str, content: str) -> None:
        """Append a message to the history list using RPUSH (Atomic)."""
        key = self.history_key(scope_id, session_id)
        packed = msgpack.packb({"role": role, "content": content})

        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, packed)
            # Guarantee history never exceeds limit (O(1) operation on tail)
            await pipe.ltrim(key, -settings.chat_history_limit, -1)
            await pipe.expire(key, settings.chat_history_redis_ttl)
            await pipe.execute()

    async def get_history(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        """Retrieve and deserialize chat history from Redis LIST."""
        key = self.history_key(scope_id, session_id)
        raw_list = await self.client.lrange(key, 0, -1)
        if not raw_list:
            return []

        history = []
        for raw in raw_list:
            try:
                history.append(msgpack.unpackb(raw))
            except Exception as e:
                logger.warning("Failed to unpack message in session %s: %s", session_id, e)
        return history

    async def history_exists(self, scope_id: str, session_id: str) -> bool:
        return await self.client.exists(self.history_key(scope_id, session_id)) > 0

    async def hydrate_from_db(self, scope_id: str, session_id: str, db_messages: list[dict]) -> None:
        """Warm up Redis cache from database using RPUSH."""
        key = self.history_key(scope_id, session_id)
        lock_key = f"{key}:hydrating"

        if not await self.client.set(lock_key, "1", nx=True, ex=30):
            return

        if not await self.history_exists(scope_id, session_id):
            formatted = [
                msgpack.packb({"role": m["role"], "content": m["content"]})
                for m in db_messages[-settings.chat_history_limit :]
            ]
            if formatted:
                async with self.client.pipeline(transaction=True) as pipe:
                    await pipe.rpush(key, *formatted)
                    await pipe.expire(key, settings.chat_history_redis_ttl)
                    await pipe.execute()

        await self.client.delete(lock_key)
