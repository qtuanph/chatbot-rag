"""Cleanup service — hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.adapters.storage import build_storage
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.celery_app import celery_app
from app.core.config import settings
from app.modules.documents.utils.document_registry import DocumentRegistry

if TYPE_CHECKING:
    from app.modules.documents.repositories import DocumentRepository, SectionRepository

logger = logging.getLogger(__name__)


class CleanupService:
    """Business logic for hard-deleting documents and all related artifacts."""

    def __init__(
        self, doc_repo: DocumentRepository, section_repo: SectionRepository, registry: DocumentRegistry
    ) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.registry = registry

    async def hard_delete_document(self, document_id: str) -> dict[str, bool]:
        """Hard-delete document and all artifacts. Order: Vectors → Sections → File → DB → Registry."""
        storage = build_storage()
        vector_store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            collection_name=settings.qdrant_collection,
            vector_size=settings.embedding_vector_size,
            timeout=settings.qdrant_timeout,
        )

        record = await self.registry.get_by_document_id(document_id)

        # ── Execution (Strict 6-step order: registry → vectors → sections → file → DB row → purge) ──
        # 1. Registry mark (Redis)
        await self.registry.delete(document_id)

        # 2. Vectors (Qdrant)
        await vector_store.delete(document_id)

        # 3. Sections (PostgreSQL)
        await self.section_repo.delete_sections(document_id)

        # 4. Delete entire document folder from S3 (original file + OCR md + any future artifacts)
        try:
            await asyncio.to_thread(storage.delete_prefix, f"{document_id}/")
        except Exception as e:
            logger.warning("Failed to delete document folder from S3: %s", e)

        # 5. Document DB row (PostgreSQL)
        db_deleted = await self.doc_repo.hard_delete(document_id)

        # 6. Final registry purge (Redis)
        if record:
            await asyncio.to_thread(celery_app.backend.delete, record.task_id)

        await self.registry.purge_async(document_id)

        from app.modules.chat.retrieval.retrieval_service import RetrievalService

        retrieval_svc = RetrievalService(redis_client=self.registry.client)
        await retrieval_svc.invalidate_doc_ids_cache()

        from app.modules.system.tasks import rebuild_bm25_index_task

        rebuild_bm25_index_task.delay()

        return {"deleted": db_deleted, "document_id": document_id}
