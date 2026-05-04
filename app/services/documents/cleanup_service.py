"""Cleanup service — hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

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

    def hard_delete_document(self, document_id: str) -> dict[str, bool]:
        """
        Hard-delete a document and all related artifacts.

        Deletion order (important — do not reorder):
          1. Mark deleted in registry first → /status reflects 'deleted' immediately
          2. Delete vectors from Qdrant → retrieval stops working
          3. Delete sections from PostgreSQL
          4. Delete file from object storage (RustFS/S3)
          5. Delete DB row → record gone
          6. Purge all registry keys → cleanup Redis last
        """
        storage = build_storage()
        vector_store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            collection_name=settings.qdrant_collection,
            vector_size=settings.embedding_vector_size,
            timeout=settings.qdrant_timeout,
        )

        object_uri: str | None = None
        db_deleted = False
        storage_deleted = False
        vectors_deleted = False
        registry_deleted = False
        sections_deleted = False
        critical_errors: list[str] = []

        record = registry.get_by_document_id(document_id)

        # ── Step 1: Mark deleted in registry FIRST ───────────────────────────────
        try:
            registry.delete(document_id)
        except Exception:
            logger.warning("Failed to mark registry deleted for document %s", document_id, exc_info=True)

        # ── Step 2: Delete vectors ───────────────────────────────────────────────
        try:
            vector_store.delete(document_id)
            vectors_deleted = True
        except Exception:
            critical_errors.append("vectors")
            logger.warning("Failed to delete vectors for document %s", document_id, exc_info=True)

        # ── Step 3: Delete sections from PostgreSQL ──────────────────────────────
        try:
            count = self.section_repo.delete_sections(document_id)
            sections_deleted = True
            if count > 0:
                logger.info("Deleted %d sections for document %s", count, document_id)
        except Exception:
            critical_errors.append("sections")
            logger.warning("Failed to delete sections for document %s", document_id, exc_info=True)

        # ── Step 4: Delete file from object storage ─────────────────────────────
        if record is not None:
            object_uri = record.object_uri
        if object_uri is None:
            doc = self.doc_repo.get_full_document(document_id)
            if doc is not None:
                object_uri = doc.get("file_path")

        if object_uri and hasattr(storage, "delete_object"):
            try:
                storage.delete_object(object_uri)
                storage_deleted = True
            except Exception:
                logger.warning(
                    "Failed to delete object storage file for document %s",
                    document_id,
                    exc_info=True,
                )

        # ── Step 5: Delete DB row ────────────────────────────────────────────────
        try:
            db_deleted = self.doc_repo.hard_delete(document_id)
        except Exception:
            critical_errors.append("db_row")
            logger.warning("Failed to delete DB row for document %s", document_id, exc_info=True)

        # ── Step 6: Purge Celery result + all Redis registry keys ────────────────
        if record is not None:
            try:
                celery_app.backend.delete(record.task_id)
            except Exception:
                logger.warning(
                    "Failed to delete Celery backend result for document %s",
                    document_id,
                    exc_info=True,
                )

        registry.purge(document_id)
        registry_deleted = True

        # Invalidate cached doc IDs so next chat request no longer sees deleted doc
        from app.services.retrieval.retrieval_service import invalidate_doc_ids_cache

        invalidate_doc_ids_cache()

        # Rebuild BM25 index — IDF values changed after document removal
        try:
            from app.workers.maintenance_tasks import rebuild_bm25_index_task

            rebuild_bm25_index_task.delay()
            logger.info("BM25 index rebuild dispatched after deleting document %s", document_id)
        except Exception:
            logger.warning(
                "BM25 rebuild dispatch failed after deleting document %s",
                document_id,
                exc_info=True,
            )

        # Critical failure: both DB row and vectors failed → document is in broken state
        if "db_row" in critical_errors and "vectors" in critical_errors:
            raise RuntimeError(
                f"Hard-delete partially failed for {document_id}: {', '.join(critical_errors)}. "
                "Document is in an inconsistent state."
            )

        return {
            "db_deleted": db_deleted,
            "sections_deleted": sections_deleted,
            "storage_deleted": storage_deleted,
            "vectors_deleted": vectors_deleted,
            "registry_deleted": registry_deleted,
        }
