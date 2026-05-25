"""Cleanup service — hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from app.adapters.storage import build_storage
from app.core.llama_index import build_vector_store

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
        """Hard-delete document. Order (per AGENTS.md): Vectors → Sections → File → DB."""
        storage = build_storage()
        # Cleanup path only needs delete by ref_doc_id; disable hybrid to avoid
        # unnecessary sparse model initialization/download.
        vector_store = build_vector_store(enable_hybrid=False)

        # 1. Vectors (Qdrant via LlamaIndex)
        try:
            await vector_store.adelete(ref_doc_id=document_id)
        except Exception as e:
            logger.warning("[%s] Vector delete warning: %s", document_id, e)

        # 2. Sections (PostgreSQL)
        await self.section_repo.delete_sections(document_id)

        # 3. Delete entire document folder from S3
        try:
            await asyncio.to_thread(storage.delete_prefix, f"{document_id}/")
        except Exception as e:
            logger.warning("Failed to delete document folder from S3: %s", e)

        # 4. Document DB row (PostgreSQL)
        db_deleted = await self.doc_repo.hard_delete(document_id)

        # 5. Clean up Redis task mapping
        if self.redis:
            try:
                # redis client here is sync (from get_sync_redis_client), run in thread.
                keys = await asyncio.to_thread(self.redis.keys, f"task:doc:*{document_id}*")
                if keys:
                    await asyncio.to_thread(self.redis.delete, *keys)
            except Exception as e:
                logger.warning("[%s] Failed to clean task keys from Redis: %s", document_id, e)

        return {"deleted": db_deleted, "document_id": document_id}
