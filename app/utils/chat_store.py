from redis import asyncio as aioredis
from app.core.config import settings


class ChatStore:
    """Manages chat history using standard RedisJSON (from redis-py)."""

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        if client:
            self.client = client
        else:
            self.client = aioredis.from_url(settings.redis_url, decode_responses=True)

    def active_key(self, scope_id: str) -> str:
        return f"chat:active:{scope_id}"

    def history_key(self, scope_id: str, session_id: str) -> str:
        return f"chat:history:{scope_id}:{session_id}"

    async def set_active_session(self, scope_id: str, session_id: str) -> None:
        await self.client.set(self.active_key(scope_id), session_id)

    async def get_active_session(self, scope_id: str) -> str | None:
        return await self.client.get(self.active_key(scope_id))

    async def append_message(self, scope_id: str, session_id: str, role: str, content: str) -> None:
        key = self.history_key(scope_id, session_id)
        msg = {"role": role, "content": content}

        if not await self.client.exists(key):
            await self.client.json().set(key, "$", [msg])
        else:
            await self.client.json().arrappend(key, "$", msg)
        await self.client.expire(key, settings.chat_history_redis_ttl)

    async def get_history(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        history = await self.client.json().get(self.history_key(scope_id, session_id))
        return history if history else []

    async def history_exists(self, scope_id: str, session_id: str) -> bool:
        return await self.client.exists(self.history_key(scope_id, session_id)) > 0

    async def hydrate_from_db(self, scope_id: str, session_id: str, db_messages: list[dict]) -> None:
        key = self.history_key(scope_id, session_id)
        lock_key = f"{key}:hydrating"

        if not await self.client.set(lock_key, "1", nx=True, ex=30):
            return

        if not await self.history_exists(scope_id, session_id):
            formatted = [
                {"role": m["role"], "content": m["content"]} for m in db_messages[-settings.chat_history_limit :]
            ]
            await self.client.json().set(key, "$", formatted)
            await self.client.expire(key, settings.chat_history_redis_ttl)

        await self.client.delete(lock_key)
