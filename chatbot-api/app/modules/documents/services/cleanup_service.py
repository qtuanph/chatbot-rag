"""Cleanup service — hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from app.adapters.storage import build_storage
from app.core.llama_index import delete_document_vectors

if TYPE_CHECKING:
    from app.modules.documents.repositories import DocumentRepository, SectionRepository

logger = logging.getLogger(__name__)


class CleanupService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        section_repo: SectionRepository,
        redis_client: Any | None = None,
    ) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.redis = redis_client

    async def hard_delete_document(self, document_id: str) -> dict[str, bool]:
        """Hard-delete document. Order (per AGENTS.md & 2.3_WORKFLOWS_DELETE.md):
        1. registry.delete() -> Marks deleted in Redis status
        2. Vectors (Qdrant via LlamaIndex)
        3. Sections (PostgreSQL)
        4. Storage (RustFS/S3 file prefix)
        5. Document DB row (PostgreSQL)
        6. registry.purge() -> Purges task registry keys
        """
        storage = build_storage()

        # 1. registry.delete(): Update Redis status so /status immediately returns 'deleted'
        if self.redis:
            try:

                def _mark_deleted_in_redis():
                    for key in self.redis.scan_iter(f"task:doc:*{document_id}*"):
                        try:
                            self.redis.hset(key, mapping={"status": "deleted", "stage": "deleted"})
                        except Exception:
                            pass

                await asyncio.to_thread(_mark_deleted_in_redis)
            except Exception as e:
                logger.warning("[%s] Failed to set deleted status in Redis registry: %s", document_id, e)

        # 2. Vectors (Qdrant via LlamaIndex)
        try:
            await delete_document_vectors(document_id)
        except Exception as e:
            logger.warning("[%s] Vector delete warning: %s", document_id, e)

        # 3. Sections (PostgreSQL)
        await self.section_repo.delete_sections(document_id)

        # 4. Delete entire document folder from S3 / RustFS
        try:
            await asyncio.to_thread(storage.delete_prefix, f"{document_id}/")
        except Exception as e:
            logger.warning("Failed to delete document folder from S3: %s", e)

        # 5. Document DB row (PostgreSQL)
        db_deleted = await self.doc_repo.hard_delete(document_id)

        # 6. registry.purge(): Clean up all task registry keys from Redis
        if self.redis:
            try:
                # redis client here is sync (from get_sync_redis_client), run in thread.
                def _scan_and_delete():
                    keys = list(self.redis.scan_iter(f"task:doc:*{document_id}*"))
                    if keys:
                        self.redis.delete(*keys)
                    return len(keys)

                await asyncio.to_thread(_scan_and_delete)
            except Exception as e:
                logger.warning("[%s] Failed to clean task keys from Redis: %s", document_id, e)

        return {"deleted": db_deleted, "document_id": document_id}
