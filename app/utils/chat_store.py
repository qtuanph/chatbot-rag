from __future__ import annotations

import json

import redis

from app.core.config import settings


class ChatStore:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def active_key(self, scope_id: str) -> str:
        return f"chat:active:{scope_id}"

    def history_key(self, scope_id: str, session_id: str) -> str:
        return f"chat:history:{scope_id}:{session_id}"

    def set_active_session(self, scope_id: str, session_id: str) -> None:
        self.client.set(self.active_key(scope_id), session_id)

    def get_active_session(self, scope_id: str) -> str | None:
        return self.client.get(self.active_key(scope_id))

    def append_message(self, scope_id: str, session_id: str, role: str, content: str) -> None:
        key = self.history_key(scope_id, session_id)
        payload = json.dumps({"role": role, "content": content})
        pipe = self.client.pipeline()
        pipe.rpush(key, payload)
        pipe.expire(key, settings.chat_history_redis_ttl)
        pipe.execute()

    def get_history(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        items = self.client.lrange(self.history_key(scope_id, session_id), 0, -1)
        return [json.loads(item) for item in items]

    def history_exists(self, scope_id: str, session_id: str) -> bool:
        """Check if Redis has history for this session (avoids unnecessary DB query)."""
        return self.client.llen(self.history_key(scope_id, session_id)) > 0

    def hydrate_from_db(self, scope_id: str, session_id: str, db_messages: list[dict]) -> None:
        """Load DB messages into Redis if TTL expired (key empty or missing)."""
        key = self.history_key(scope_id, session_id)
        if self.client.llen(key) > 0:
            return
        for msg in db_messages[-settings.chat_history_limit :]:
            payload = json.dumps({"role": msg["role"], "content": msg["content"]})
            self.client.rpush(key, payload)
        self.client.expire(key, settings.chat_history_redis_ttl)
