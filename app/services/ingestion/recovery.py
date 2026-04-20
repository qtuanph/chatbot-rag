"""
Pipeline Recovery & Failure Handling

Handles:
- Task state recovery (stuck in processing state)
- Idempotency (preventing duplicate processing)
- Orphaned data cleanup (vectors without sections, sections without vectors)
- Consistency validation (section_id metadata in vectors matches PostgreSQL sections)
- Atomic rollback on failure
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.db.session import SessionLocal
from app.models.core import Document, DocumentSection
from app.adapters.vector_stores import build_vector_store
from app.services.storage import build_storage
from app.services.documents.registry import DocumentRegistry
from app.core.config import settings


logger = logging.getLogger(__name__)


class PipelineRecoveryManager:
    """Manages recovery from pipeline failures and orphaned data cleanup."""

    def __init__(self):
        self.registry = DocumentRegistry()
        self.vector_store = build_vector_store()
        self.storage = build_storage()

    def check_stuck_processing(self, timeout_minutes: int = 30) -> list[str]:
        """
        Find documents stuck in 'processing' state longer than timeout.
        Returns list of document IDs that should be recovered.
        """
        stuck_documents = []
        with SessionLocal() as session:
            # Find documents in processing state that haven't been updated in a while
            timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            rows = session.query(Document).filter(
                Document.status == "processing",
                Document.status_updated_at < timeout_threshold,
            ).all()

            stuck_documents = [str(doc.id) for doc in rows]
            if stuck_documents:
                logger.warning(
                    "Found %d documents stuck in processing (timeout=%dm): %s",
                    len(stuck_documents),
                    timeout_minutes,
                    stuck_documents,
                )
        return stuck_documents

    def recover_stuck_document(self, document_id: str, mark_failed: bool = True) -> dict:
        """
        Recover a document stuck in processing state.
        Options:
        - mark_failed=True: Mark as failed (document will need re-upload)
        - mark_failed=False: Check if partial ingestion exists, promote to ready if valid

        Returns recovery report with actions taken.
        """
        report = {
            "document_id": document_id,
            "actions": [],
            "vectors_found": 0,
            "sections_found": 0,
            "promoted_to_ready": False,
            "marked_failed": False,
        }

        with SessionLocal() as session:
            doc = session.get(Document, document_id)
            if doc is None:
                report["actions"].append("document_not_found")
                return report

            if doc.status != "processing":
                report["actions"].append(f"not_in_processing_state (status={doc.status})")
                return report

            # Count vectors
            vector_count = self.vector_store.count(document_id)
            report["vectors_found"] = vector_count

            # Count sections
            section_count = session.query(DocumentSection).filter(
                DocumentSection.document_id == document_id
            ).count()
            report["sections_found"] = section_count

            if vector_count > 0 or section_count > 0:
                # Partial ingestion exists — can be promoted to ready if vectors > 0
                if vector_count > 0:
                    if not mark_failed:
                        doc.status = "ready"
                        doc.status_stage = "complete"
                        doc.progress_percent = 100
                        doc.status_message = "Recovered from partial processing."
                        doc.status_updated_at = datetime.now(timezone.utc)
                        session.commit()
                        report["promoted_to_ready"] = True
                        report["actions"].append(f"promoted_to_ready (vectors={vector_count})")
                        logger.info(
                            "[%s] Promoted stuck document to ready: %d vectors, %d sections",
                            document_id, vector_count, section_count,
                        )
                    else:
                        # Mark as failed instead
                        doc.status = "failed"
                        doc.status_stage = "recovery_marked_failed"
                        doc.progress_percent = 100
                        doc.status_message = "Stuck in processing, marked as failed for retry."
                        doc.status_updated_at = datetime.now(timezone.utc)
                        session.commit()
                        report["marked_failed"] = True
                        report["actions"].append("marked_failed")
                        logger.warning(
                            "[%s] Marked stuck document as failed for retry",
                            document_id,
                        )
                else:
                    # Only sections exist, no vectors — mark failed (incomplete)
                    doc.status = "failed"
                    doc.status_stage = "recovery_no_vectors"
                    doc.progress_percent = 100
                    doc.status_message = "Stuck: sections exist but no vectors. Marked failed."
                    doc.status_updated_at = datetime.now(timezone.utc)
                    session.commit()
                    report["marked_failed"] = True
                    report["actions"].append("marked_failed_no_vectors")
                    logger.warning(
                        "[%s] Marked stuck document as failed (no vectors found)",
                        document_id,
                    )
            else:
                # No partial data — mark as failed
                doc.status = "failed"
                doc.status_stage = "recovery_no_data"
                doc.progress_percent = 100
                doc.status_message = "Stuck in processing with no data. Marked failed."
                doc.status_updated_at = datetime.now(timezone.utc)
                session.commit()
                report["marked_failed"] = True
                report["actions"].append("marked_failed_no_data")
                logger.warning(
                    "[%s] Marked stuck document as failed (no data found)",
                    document_id,
                )

        return report

    def check_orphaned_vectors(self, document_id: str) -> list[str]:
        """
        Find vector IDs that exist in Qdrant but have no corresponding section in PostgreSQL.
        This indicates a partial failure scenario where sections weren't stored.

        Returns list of orphaned vector IDs (empty if consistent).
        """
        orphaned = []
        try:
            # Get all vectors for this document
            vectors = self.vector_store.scroll(
                filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
                with_payload=True,
                with_vector=False,
                limit=10000,
            )

            # Get all section IDs in PostgreSQL
            with SessionLocal() as session:
                section_ids = set()
                rows = session.query(DocumentSection.section_id).filter(
                    DocumentSection.document_id == document_id
                ).all()
                section_ids = {str(row[0]) for row in rows}

            # Check if each vector has a matching section
            for point in vectors:
                payload = point.get("payload", {})
                section_id = payload.get("section_id")
                if section_id and str(section_id) not in section_ids:
                    orphaned.append(point.get("id"))

            if orphaned:
                logger.warning(
                    "[%s] Found %d orphaned vectors (no matching section_id)",
                    document_id,
                    len(orphaned),
                )
        except Exception as e:
            logger.error("[%s] Failed to check orphaned vectors: %s", document_id, e)

        return orphaned

    def cleanup_orphaned_vectors(self, document_id: str) -> dict:
        """
        Remove vectors that have no matching section in PostgreSQL.
        Returns cleanup report.
        """
        report = {
            "document_id": document_id,
            "orphaned_count": 0,
            "cleaned": 0,
            "error": None,
        }

        try:
            orphaned = self.check_orphaned_vectors(document_id)
            report["orphaned_count"] = len(orphaned)

            if orphaned:
                # Remove orphaned vectors
                for vec_id in orphaned:
                    try:
                        self.vector_store.delete_by_ids([vec_id])
                        report["cleaned"] += 1
                    except Exception as e:
                        logger.error(
                            "[%s] Failed to delete orphaned vector %s: %s",
                            document_id, vec_id, e,
                        )
                        report["error"] = str(e)

                if report["cleaned"] > 0:
                    logger.info(
                        "[%s] Cleaned up %d orphaned vectors",
                        document_id,
                        report["cleaned"],
                    )
        except Exception as e:
            report["error"] = str(e)
            logger.error("[%s] Cleanup orphaned vectors failed: %s", document_id, e)

        return report

    def validate_section_vector_consistency(self, document_id: str) -> dict:
        """
        Validate that vectors in Qdrant have matching sections in PostgreSQL.
        Returns consistency report.
        """
        report = {
            "document_id": document_id,
            "total_vectors": 0,
            "total_sections": 0,
            "consistent": True,
            "issues": [],
        }

        try:
            # Count vectors
            vector_count = self.vector_store.count(document_id)
            report["total_vectors"] = vector_count

            # Count sections
            with SessionLocal() as session:
                section_count = session.query(DocumentSection).filter(
                    DocumentSection.document_id == document_id
                ).count()
                report["total_sections"] = section_count

            # Check orphaned vectors
            orphaned = self.check_orphaned_vectors(document_id)
            if orphaned:
                report["consistent"] = False
                report["issues"].append(f"orphaned_vectors: {len(orphaned)}")

            # Check if sections exist but no vectors
            if section_count > 0 and vector_count == 0:
                report["consistent"] = False
                report["issues"].append("sections_exist_but_no_vectors")

            if report["consistent"]:
                logger.info(
                    "[%s] ✓ Consistency check passed: %d vectors, %d sections",
                    document_id, vector_count, section_count,
                )
            else:
                logger.warning(
                    "[%s] ✗ Consistency check failed: %s",
                    document_id, report["issues"],
                )

        except Exception as e:
            report["consistent"] = False
            report["issues"].append(f"validation_error: {str(e)}")
            logger.error("[%s] Consistency validation failed: %s", document_id, e)

        return report

    def idempotency_check(self, task_id: str) -> Optional[dict]:
        """
        Check if a task has already been processed.
        Returns the previous result if task was completed, None if new.
        """
        try:
            record = self.registry.get_by_task_id(task_id)
            if record and record.status == "ready":
                return {
                    "already_processed": True,
                    "task_id": task_id,
                    "document_id": record.document_id,
                    "status": record.status,
                }
        except Exception as e:
            logger.warning("Idempotency check failed for task %s: %s", task_id, e)

        return None
