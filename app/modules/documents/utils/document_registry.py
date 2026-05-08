from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class DocumentRecord:
    document_id: str
    task_id: str
    object_uri: str
    filename: str
    status: str = "queued"
    deleted: bool = False


class DocumentRegistry:
    """Document status registry using native RedisJSON for atomic state management."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self._is_async = hasattr(client, "pipeline") and callable(client.pipeline)

    def _key(self, document_id: str) -> str:
        return f"document:{document_id}"

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"

    async def put(self, record: DocumentRecord) -> None:
        """Store record using JSON.SET (Async)."""
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.json().set(self._key(record.document_id), "$", asdict(record))
            await pipe.expire(self._key(record.document_id), 86400)
            await pipe.set(self._task_key(record.task_id), record.document_id, ex=86400)
            await pipe.execute()

    async def get_by_document_id(self, document_id: str) -> DocumentRecord | None:
        """Retrieve record using JSON.GET (Async)."""
        raw = await self.client.json().get(self._key(document_id))
        if isinstance(raw, list) and raw:
            raw = raw[0]
        return DocumentRecord(**raw) if raw else None

    async def get_by_task_id(self, task_id: str) -> DocumentRecord | None:
        """Retrieve record by task_id (Async)."""
        doc_id = await self.client.get(self._task_key(task_id))
        if not doc_id:
            return None
        return await self.get_by_document_id(doc_id)

    async def delete(self, document_id: str) -> None:
        """Mark record as deleted in RedisJSON (Async)."""
        key = self._key(document_id)
        if await self.client.exists(key):
            await self.client.json().set(key, "$.deleted", True)
            await self.client.json().set(key, "$.status", "deleted")

    async def invalidate_active_ids_async(self) -> None:
        """Clear the active document IDs cache (Async)."""
        await self.client.delete("rag:active_doc_ids")

    async def get_active_ids_async(self) -> set[str] | None:
        """Retrieve cached active document IDs (Async)."""
        data = await self.client.get("rag:active_doc_ids")
        if data:
            import json

            return set(json.loads(data))
        return None

    async def set_active_ids_async(self, ids: set[str], ttl: int = 60) -> None:
        """Cache active document IDs for RAG (Async)."""
        import json

        await self.client.set("rag:active_doc_ids", json.dumps(list(ids)), ex=ttl)

    async def purge_async(self, document_id: str) -> None:
        """Remove record and task mapping from Redis (Async)."""
        record = await self.get_by_document_id(document_id)
        if record:
            await self.client.delete(self._key(document_id), self._task_key(record.task_id))
        await self.invalidate_active_ids_async()

    def put_sync(self, record: DocumentRecord) -> None:
        """Store record using JSON.SET (Sync)."""
        pipe = self.client.pipeline(transaction=True)
        pipe.json().set(self._key(record.document_id), "$", asdict(record))
        pipe.expire(self._key(record.document_id), 86400)
        pipe.set(self._task_key(record.task_id), record.document_id, ex=86400)
        pipe.execute()

    def get_by_document_id_sync(self, document_id: str) -> DocumentRecord | None:
        """Retrieve record using JSON.GET (Sync)."""
        raw = self.client.json().get(self._key(document_id))
        if isinstance(raw, list) and raw:
            raw = raw[0]
        return DocumentRecord(**raw) if raw else None

    def get_by_task_id_sync(self, task_id: str) -> DocumentRecord | None:
        """Retrieve record by task_id (Sync)."""
        doc_id = self.client.get(self._task_key(task_id))
        if not doc_id:
            return None
        return self.get_by_document_id_sync(doc_id)

    def delete_sync(self, document_id: str) -> None:
        """Mark record as deleted in RedisJSON (Sync)."""
        key = self._key(document_id)
        if self.client.exists(key):
            self.client.json().set(key, "$.deleted", True)
            self.client.json().set(key, "$.status", "deleted")

    def invalidate_active_ids_sync(self) -> None:
        """Clear the active document IDs cache (Sync)."""
        self.client.delete("rag:active_doc_ids")

    def get_active_ids_sync(self) -> set[str] | None:
        """Retrieve cached active document IDs (Sync)."""
        data = self.client.get("rag:active_doc_ids")
        if data:
            import json

            return set(json.loads(data))
        return None

    def set_active_ids_sync(self, ids: set[str], ttl: int = 60) -> None:
        """Cache active document IDs for RAG (Sync)."""
        import json

        self.client.set("rag:active_doc_ids", json.dumps(list(ids)), ex=ttl)

    def purge_sync(self, document_id: str) -> None:
        """Remove record and task mapping from Redis (Sync)."""
        record = self.get_by_document_id_sync(document_id)
        if record:
            self.client.delete(self._key(document_id), self._task_key(record.task_id))
        self.invalidate_active_ids_sync()
