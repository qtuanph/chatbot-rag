"""Celery tasks for maintenance operations — BM25 rebuild, orphan cleanup, audit logging."""

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.maintenance_tasks.rebuild_bm25_index_task",
    acks_late=True,
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_jitter=True,
    max_retries=2,
)
def rebuild_bm25_index_task() -> None:
    """Rebuild BM25 vocabulary from Qdrant. Called after document upload/delete."""
    try:
        from app.utils.bm25_index import build_bm25_index_from_qdrant

        count = build_bm25_index_from_qdrant()
        logger.info("BM25 index rebuilt: %d chunks indexed", count)
    except Exception as e:
        logger.error("BM25 index rebuild failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="app.workers.maintenance_tasks.cleanup_orphaned_vectors_task",
    acks_late=True,
    ignore_result=True,
)
def cleanup_orphaned_vectors_task() -> None:
    """Remove Qdrant vectors that have no matching section in PostgreSQL."""
    try:
        from app.services.ingestion.recovery_service import RecoveryService
        from app.repositories.document_repository import DocumentRepository
        from app.repositories.section_repository import SectionRepository

        with SessionLocal() as session:
            doc_repo = DocumentRepository(session)
            section_repo = SectionRepository(session)
            recovery = RecoveryService(doc_repo=doc_repo, section_repo=section_repo)

            doc_ids = doc_repo.get_all_document_ids()
            total_cleaned = 0
            for doc_id in doc_ids:
                result = recovery.cleanup_orphaned_vectors(document_id=doc_id)
                total_cleaned += result.get("cleaned", 0)
            logger.info(
                "Orphaned vector cleanup complete: %d vectors removed across %d documents", total_cleaned, len(doc_ids)
            )
    except Exception as e:
        logger.error("Orphaned vector cleanup failed: %s", e, exc_info=True)
        raise


@celery_app.task(
    name="app.workers.maintenance_tasks.record_audit_task",
    acks_late=True,
    ignore_result=True,
    max_retries=1,
)
def record_audit_task(
    *,
    action: str,
    user_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Fire-and-forget audit logging. Never blocks the caller."""
    try:
        from app.utils.audit import safe_record_audit

        safe_record_audit(
            action=action,
            actor_user_id=user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.warning("Audit logging failed (fire-and-forget): %s", e)
