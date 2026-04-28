"""Celery task definitions for document cleanup and maintenance."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.chat import ChatSession
from app.models.core import Document

logger = logging.getLogger(__name__)


def _verify_deletion(
    document_id: str,
    file_path: str | None,
    vector_store,
    storage,
) -> dict:
    """
    Post-delete verification: confirm vectors purged, file removed, DB row gone.

    Returns verification dict. Does NOT raise — logs WARNING on failure.
    """
    qdrant_count = vector_store.count(document_id)
    file_gone = (not storage.file_exists(file_path)) if file_path else True
    with SessionLocal() as session:
        db_gone = session.get(Document, document_id) is None

    result = {
        "qdrant_vectors_remaining": qdrant_count,
        "qdrant_clean": qdrant_count == 0,
        "file_removed": file_gone,
        "db_row_gone": db_gone,
        "passed": qdrant_count == 0 and file_gone and db_gone,
    }

    if result["passed"]:
        logger.info(
            "[%s] ✓ Deletion verified: qdrant=0 file_removed=%s db_gone=%s",
            document_id,
            file_gone,
            db_gone,
        )
    else:
        logger.warning(
            "[%s] ✗ Deletion verify FAILED: qdrant_remaining=%d file_removed=%s db_gone=%s",
            document_id,
            qdrant_count,
            file_gone,
            db_gone,
        )

    return result


@celery_app.task(
    name="app.workers.cleanup_pipeline.delete_document_task",
    bind=True,
    acks_late=True,
)
def delete_document_task(self, task_id: str, document_id: str, user_id: str | None = None) -> dict:
    """
    Celery task: hard-delete document + all artifacts → verify cleanup.

    Steps: registry → vectors → file → DB row → registry purge → verify.
    """
    self.update_state(
        task_id=task_id,
        state="STARTED",
        meta={
            "stage": "delete",
            "progress": {"step": "delete", "percent": 20},
            "document_id": document_id,
        },
    )

    # Lazy imports — avoid loading heavy modules (qdrant, storage, cleanup)
    # unless this task actually runs
    from app.adapters.vector_stores.qdrant import QdrantVectorStore
    from app.services.storage import build_storage
    from app.services.documents.cleanup import hard_delete_document

    storage = build_storage()
    # Resolve file_path before hard_delete removes the DB row
    file_path: str | None = None
    with SessionLocal() as session:
        doc = session.get(Document, document_id)
        if doc is not None:
            file_path = doc.file_path

    cleanup_result = hard_delete_document(document_id)

    # ── Post-delete verification ──────────────────────────────────────────────
    # Build a minimal vector_store (no embedding needed for count/verify)
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=1,  # dimension irrelevant for count — collection already exists
        timeout=settings.qdrant_timeout,
    )
    verify = _verify_deletion(document_id, file_path, vector_store, storage)

    return {
        "task_id": task_id,
        "document_id": document_id,
        "status": "deleted",
        "stage": "deleted",
        "progress": {"step": "deleted", "percent": 100},
        "requested_by": user_id,
        "cleanup": cleanup_result,
        "verification": verify,
    }


@celery_app.task(
    name="app.workers.cleanup_pipeline.cleanup_old_chat_sessions_task",
    acks_late=True,
)
def cleanup_old_chat_sessions_task() -> dict:
    """
    Periodic task: delete chat sessions older than chat_session_ttl_days.

    Messages are cascade-deleted via ON DELETE CASCADE on chat_messages.session_id.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.chat_session_ttl_days)
    logger.info("Cleaning up chat sessions older than %s (TTL=%d days)", cutoff, settings.chat_session_ttl_days)

    with SessionLocal() as session:
        stmt = sa_delete(ChatSession).where(
            ChatSession.created_at < cutoff,
        )
        result = session.execute(stmt)
        session.commit()
        count = result.rowcount

    logger.info("Cleaned up %d old chat sessions", count)
    return {"deleted_count": count, "cutoff": cutoff.isoformat()}
