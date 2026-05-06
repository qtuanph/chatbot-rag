from __future__ import annotations

from dataclasses import dataclass, asdict
import redis.asyncio as redis

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
    """Document status registry using native RedisJSON for atomic state management."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    def _key(self, document_id: str) -> str:
        return f"document:{document_id}"

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"

    async def put(self, record: DocumentRecord) -> None:
        """Store record using JSON.SET."""
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.json().set(self._key(record.document_id), "$", asdict(record))
            await pipe.expire(self._key(record.document_id), 86400)
            await pipe.set(self._task_key(record.task_id), record.document_id, ex=86400)
            await pipe.execute()

    async def get_by_document_id(self, document_id: str) -> DocumentRecord | None:
        """Retrieve record using JSON.GET."""
        raw = await self.client.json().get(self._key(document_id))
        return DocumentRecord(**raw) if raw else None

    async def get_by_task_id(self, task_id: str) -> DocumentRecord | None:
        """Resolve document_id from task_id and return record."""
        document_id = await self.client.get(self._task_key(task_id))
        return await self.get_by_document_id(document_id.decode() if isinstance(document_id, bytes) else document_id) if document_id else None

    async def update(self, record: DocumentRecord) -> None:
        await self.put(record)

    async def delete(self, document_id: str) -> None:
        """Mark record as deleted in RedisJSON."""
        key = self._key(document_id)
        if await self.client.exists(key):
            await self.client.json().set(key, "$.deleted", True)
            await self.client.json().set(key, "$.status", "deleted")

    async def get_active_ids_async(self) -> set[str]:
        """Return cached active document IDs (Async). Decode bytes to strings if needed."""
        members = await self.client.smembers("rag:active_doc_ids")
        return {m.decode() if isinstance(m, bytes) else m for m in members}

    async def set_active_ids_async(self, ids: list[str] | set[str]) -> None:
        """Cache active document IDs (Async)."""
        if ids:
            async with self.client.pipeline(transaction=True) as pipe:
                await pipe.sadd("rag:active_doc_ids", *list(ids))
                await pipe.expire("rag:active_doc_ids", int(settings.doc_ids_cache_ttl))
                await pipe.execute()

    async def invalidate_active_ids_async(self) -> None:
        """Clear the active document IDs cache (Async)."""
        await self.client.delete("rag:active_doc_ids")

    async def purge_async(self, document_id: str) -> None:
        """Remove record and task mapping from Redis (Async)."""
        record = await self.get_by_document_id(document_id)
        if record:
            await self.client.delete(self._key(document_id), self._task_key(record.task_id))
        await self.invalidate_active_ids_async()
