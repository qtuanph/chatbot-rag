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
        payload = json.dumps({"role": role, "content": content})
        self.client.rpush(self.history_key(scope_id, session_id), payload)
        self.client.expire(self.history_key(scope_id, session_id), 24 * 60 * 60)

    def get_history(self, scope_id: str, session_id: str) -> list[dict[str, str]]:
        items = self.client.lrange(self.history_key(scope_id, session_id), 0, -1)
        return [json.loads(item) for item in items]

    def reset_chat(self, scope_id: str) -> None:
        active = self.get_active_session(scope_id)
        if active:
            self.client.delete(self.history_key(scope_id, active))
        self.client.delete(self.active_key(scope_id))
