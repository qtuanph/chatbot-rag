"""Shared hard-delete workflow for documents and related artifacts."""

from __future__ import annotations

import logging

from app.adapters.vector_stores.qdrant import QdrantVectorStore
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import Document
from app.services.registry import DocumentRegistry
from app.services.storage import build_storage


logger = logging.getLogger(__name__)
registry = DocumentRegistry()


def hard_delete_document(document_id: str) -> dict[str, bool]:
    """Hard-delete DB row, object storage blob, vectors, and registry entries."""
    storage = build_storage()
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        timeout=settings.qdrant_timeout,
    )

    object_uri: str | None = None
    db_deleted = False
    storage_deleted = False
    vectors_deleted = False
    registry_deleted = False

    record = registry.get_by_document_id(document_id)

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is not None:
            object_uri = document.file_path
            session.delete(document)
            session.commit()
            db_deleted = True

    if object_uri is None and record is not None:
        object_uri = record.object_uri

    if object_uri and hasattr(storage, "delete_object"):
        try:
            storage.delete_object(object_uri)
            storage_deleted = True
        except Exception:
            logger.warning("Failed to delete object storage file for document %s", document_id, exc_info=True)

    try:
        vector_store.delete(document_id)
        vectors_deleted = True
    except Exception:
        logger.warning("Failed to delete vectors for document %s", document_id, exc_info=True)

    if record is not None:
        try:
            celery_app.backend.delete(record.task_id)
        except Exception:
            logger.warning("Failed to delete Celery backend result for document %s", document_id, exc_info=True)

    registry.purge(document_id)
    registry_deleted = True

    return {
        "db_deleted": db_deleted,
        "storage_deleted": storage_deleted,
        "vectors_deleted": vectors_deleted,
        "registry_deleted": registry_deleted,
    }
