"""Cleanup service — hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.adapters.storage import build_storage
from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.celery_app import celery_app
from app.core.config import settings
from app.utils.document_registry import DocumentRegistry

if TYPE_CHECKING:
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.section_repository import SectionRepository

logger = logging.getLogger(__name__)
registry = DocumentRegistry()


class CleanupService:
    """Business logic for hard-deleting documents and all related artifacts."""

    def __init__(self, doc_repo: DocumentRepository, section_repo: SectionRepository) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo

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

        record = await registry.get_by_document_id(document_id)
        object_uri = record.object_uri if record else None
        if not object_uri:
            doc = await self.doc_repo.get_full_document(document_id)
            object_uri = doc.get("file_path") if doc else None

        # ── Execution (Direct, no silent fallbacks) ────────────────
        await vector_store.delete(document_id)
        
        await self.section_repo.delete_sections(document_id)

        if object_uri:
            await asyncio.to_thread(storage.delete_object, object_uri)

        db_deleted = await self.doc_repo.hard_delete(document_id)

        if record:
            await asyncio.to_thread(celery_app.backend.delete, record.task_id)

        await registry.purge_async(document_id)
        
        from app.services.retrieval.retrieval_service import invalidate_doc_ids_cache
        invalidate_doc_ids_cache()

        from app.workers.maintenance_tasks import rebuild_bm25_index_task
        rebuild_bm25_index_task.delay()

        return {"deleted": db_deleted, "document_id": document_id}
