from __future__ import annotations
import time
from typing import Any


class TokenBlacklist:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def revoke(self, jti: str, expires_at: int) -> None:
        """Revoke a token by adding its jti to the Redis blacklist."""
        now = int(time.time())
        ttl = expires_at - now
        if ttl > 0:
            await self.client.setex(f"blacklist:{jti}", ttl, "1")

    async def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked."""
        val = await self.client.get(f"blacklist:{jti}")
        return val is not None
