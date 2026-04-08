from __future__ import annotations

import redis

from app.core.config import settings


class RequestThrottle:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, window_seconds)
        return count <= limit
