from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as redis

from app.core.config import settings


class TokenBlacklist:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, jti: str) -> str:
        return f"auth:blacklist:{jti}"

    async def revoke(self, jti: str, expires_at: int) -> None:
        ttl = max(expires_at - int(datetime.now(timezone.utc).timestamp()), 1)
        await self.client.set(self._key(jti), "1", ex=ttl)

    async def is_revoked(self, jti: str) -> bool:
        return await self.client.exists(self._key(jti)) == 1
