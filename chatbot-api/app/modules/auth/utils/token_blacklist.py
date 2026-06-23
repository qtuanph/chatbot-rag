from __future__ import annotations

import redis.asyncio as redis
from app.utils.datetime_utils import utc_now


class TokenBlacklist:
    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    def _key(self, jti: str) -> str:
        return f"auth:blacklist:{jti}"

    async def revoke(self, jti: str, expires_at: int) -> None:
        ttl = max(expires_at - int(utc_now().timestamp()), 1)
        await self.client.set(self._key(jti), "1", ex=ttl)

    async def is_revoked(self, jti: str) -> bool:
        return await self.client.exists(self._key(jti)) == 1
