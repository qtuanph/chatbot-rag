from __future__ import annotations

import json
from dataclasses import dataclass, asdict

import redis

from app.core.config import settings


@dataclass
class DocumentRecord:
    document_id: str
    task_id: str
    object_uri: str
    filename: str
    status: str = "queued"
    deleted: bool = False


class DocumentRegistry:
    def __init__(self) -> None:
        self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, document_id: str) -> str:
        return f"document:{document_id}"

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"

    def put(self, record: DocumentRecord) -> None:
        payload = json.dumps(asdict(record))
        self.client.set(self._key(record.document_id), payload)
        self.client.set(self._task_key(record.task_id), record.document_id)

    def get_by_document_id(self, document_id: str) -> DocumentRecord | None:
        raw = self.client.get(self._key(document_id))
        if not raw:
            return None
        return DocumentRecord(**json.loads(raw))

    def get_by_task_id(self, task_id: str) -> DocumentRecord | None:
        document_id = self.client.get(self._task_key(task_id))
        if not document_id:
            return None
        return self.get_by_document_id(document_id)

    def update(self, record: DocumentRecord) -> None:
        self.put(record)

    def delete(self, document_id: str) -> None:
        record = self.get_by_document_id(document_id)
        if record:
            record.deleted = True
            record.status = "deleted"
            self.put(record)
