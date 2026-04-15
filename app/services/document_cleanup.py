"""Shared hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import logging

from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document, DocumentSection
from app.services.registry import DocumentRegistry
from app.services.storage import build_storage


logger = logging.getLogger(__name__)
registry = DocumentRegistry()


def hard_delete_document(document_id: str) -> dict[str, bool]:
    """
    Hard-delete a document and all related artifacts.

    Deletion order (important — do not reorder):
      1. Mark deleted in registry first → /status reflects 'deleted' immediately
      2. Delete vectors from Qdrant → retrieval stops working
      3. Delete file from object storage (RustFS/S3)
      4. Delete DB row → record gone
      5. Purge all registry keys → cleanup Redis last

    This order ensures no new chat responses reference the deleted document
    even if steps 3-5 are still in progress.
    """
    storage = build_storage()
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=1,       # placeholder — collection already exists, only used on creation
        timeout=settings.qdrant_timeout,
    )

    object_uri: str | None = None
    db_deleted = False
    storage_deleted = False
    vectors_deleted = False
    registry_deleted = False

    record = registry.get_by_document_id(document_id)

    # ── Step 1: Mark deleted in registry FIRST ───────────────────────────────
    # /status endpoint reads from registry → will immediately return 'deleted'
    try:
        registry.delete(document_id)   # sets deleted=True, status='deleted'
    except Exception:
        logger.warning("Failed to mark registry deleted for document %s", document_id, exc_info=True)

    # ── Step 2: Delete vectors ───────────────────────────────────────────────
    try:
        vector_store.delete(document_id)
        vectors_deleted = True
    except Exception:
        logger.warning("Failed to delete vectors for document %s", document_id, exc_info=True)

    # ── Step 3: Resolve object URI and delete file from object storage ───────
    if object_uri is None and record is not None:
        object_uri = record.object_uri

    if object_uri is None:
        # Fallback: read URI from DB before deleting the row
        with SessionLocal() as session:
            doc = session.get(Document, document_id)
            if doc is not None:
                object_uri = doc.file_path

    if object_uri and hasattr(storage, "delete_object"):
        try:
            storage.delete_object(object_uri)
            storage_deleted = True
        except Exception:
            logger.warning(
                "Failed to delete object storage file for document %s",
                document_id, exc_info=True,
            )

    # ── Step 3.5: Delete sections from PostgreSQL ──────────────────────────────
    sections_deleted = False
    try:
        with SessionLocal() as session:
            count = session.query(DocumentSection).filter(
                DocumentSection.document_id == document_id
            ).delete()
            session.commit()
            sections_deleted = True
            if count > 0:
                logger.info("Deleted %d sections for document %s", count, document_id)
    except Exception:
        logger.warning("Failed to delete sections for document %s", document_id, exc_info=True)

    # ── Step 4: Delete DB row ────────────────────────────────────────────────
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is not None:
            session.delete(document)
            session.commit()
            db_deleted = True

    # ── Step 5: Purge Celery result + all Redis registry keys ────────────────
    if record is not None:
        try:
            celery_app.backend.delete(record.task_id)
        except Exception:
            logger.warning(
                "Failed to delete Celery backend result for document %s",
                document_id, exc_info=True,
            )

    registry.purge(document_id)   # removes all remaining Redis keys
    registry_deleted = True

    return {
        "db_deleted": db_deleted,
        "sections_deleted": sections_deleted,
        "storage_deleted": storage_deleted,
        "vectors_deleted": vectors_deleted,
        "registry_deleted": registry_deleted,
    }
