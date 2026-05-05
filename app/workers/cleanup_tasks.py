"""Celery task definitions for document cleanup and maintenance."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.chat_repository import ChatRepository
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


async def _verify_deletion_async(
    document_id: str,
    file_path: str | None,
    vector_store,
    storage,
) -> dict:
    """
    Post-delete verification: confirm vectors purged, file removed, DB row gone.
    """
    qdrant_count = await vector_store.count(document_id)
    file_gone = await asyncio.to_thread(storage.file_exists, file_path) if file_path else True
    with SessionLocal() as session:
        doc_repo = DocumentRepository(session)
    db_gone = asyncio.run(doc_repo.get_full_document(document_id)) is None

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
    name="app.workers.cleanup_tasks.delete_document_task",
    bind=True,
    acks_late=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=max(settings.celery_retry_backoff // 3, 5),
    retry_jitter=True,
    max_retries=settings.celery_max_retries,
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
            "stage": "deleting",
            "progress": {"step": "delete", "percent": 20},
            "document_id": document_id,
        },
    )

    try:
        # Lazy imports — avoid loading heavy modules (qdrant, storage, cleanup)
        # unless this task actually runs
        from app.adapters.vector_stores.qdrant import QdrantVectorStore
        from app.adapters.storage import build_storage
        from app.services.documents.cleanup_service import CleanupService
        from app.repositories.document_repository import DocumentRepository
        from app.repositories.section_repository import SectionRepository

        storage = build_storage()
        with SessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)

            doc_info = asyncio.run(doc_repo.get_full_document(document_id))
            file_path = doc_info.get("file_path") if doc_info else None

            cleanup_svc = CleanupService(doc_repo=doc_repo, section_repo=section_repo)
            cleanup_result = asyncio.run(cleanup_svc.hard_delete_document(document_id))

        # ── Post-delete verification ──────────────────────────────────────────────
        # Build a minimal vector_store (no embedding needed for count/verify)
        vector_store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            collection_name=settings.qdrant_collection,
            vector_size=1,  # dimension irrelevant for count — collection already exists
            timeout=settings.qdrant_timeout,
        )
        # Use asyncio.run for sync Celery context
        verify = asyncio.run(_verify_deletion_async(document_id, file_path, vector_store, storage))

        return {
            "task_id": task_id,
            "document_id": document_id,
            "status": "deleted",
            "stage": "deleting",
            "progress": {"step": "deleted", "percent": 100},
            "requested_by": user_id,
            "cleanup": cleanup_result,
            "verification": verify,
        }

    except SoftTimeLimitExceeded:
        logger.error("[%s] Delete task exceeded soft time limit", document_id)
        raise


@celery_app.task(
    name="app.workers.cleanup_tasks.cleanup_old_chat_sessions_task",
    acks_late=True,
    ignore_result=True,  # Fire-and-forget beat task — no result stored
)
def cleanup_old_chat_sessions_task() -> dict:
    """
    Periodic task: delete chat sessions older than chat_session_ttl_days.

    Messages are cascade-deleted via ON DELETE CASCADE on chat_messages.session_id.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.chat_session_ttl_days)
    logger.info("Cleaning up chat sessions older than %s (TTL=%d days)", cutoff, settings.chat_session_ttl_days)

    with SessionLocal() as session:
        chat_repo = ChatRepository(session)
        count = asyncio.run(chat_repo.delete_sessions_older_than(cutoff))

    logger.info("Cleaned up %d old chat sessions", count)
    return {"deleted_count": count, "cutoff": cutoff.isoformat()}
