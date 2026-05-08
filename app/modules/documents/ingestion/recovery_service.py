"""Pipeline recovery service — handles stuck tasks, orphaned data, and consistency checks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.adapters.storage import build_storage
from app.adapters.vector_stores import build_vector_store
from app.modules.documents.utils.document_registry import DocumentRegistry

if TYPE_CHECKING:
    from app.modules.documents.repositories import DocumentRepository, SectionRepository

logger = logging.getLogger(__name__)


class RecoveryService:
    """Manages recovery from pipeline failures and orphaned data cleanup."""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        section_repo: SectionRepository,
        redis_client: Any,
        vector_store: Any | None = None,
    ) -> None:
        """
        Initialize RecoveryService with strict Dependency Injection.
        Explicitly requires redis_client to avoid event loop conflicts.
        """
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.registry = DocumentRegistry(redis_client)
        self.vector_store = vector_store
        self.storage = build_storage()

    async def initialize(self) -> RecoveryService:
        """Asynchronously initialize dependencies like vector_store if not provided."""
        if self.vector_store is None:
            self.vector_store = await build_vector_store()
        return self

    async def check_stuck_processing(self, timeout_minutes: int = 30) -> list[str]:
        """Find documents stuck in 'processing' state longer than timeout."""
        stuck_documents = await self._find_stuck_documents(timeout_minutes)
        if stuck_documents:
            logger.warning(
                "Found %d documents stuck in processing (timeout=%dm): %s",
                len(stuck_documents),
                timeout_minutes,
                stuck_documents,
            )
        return stuck_documents

    async def recover_stuck_document(self, document_id: str, mark_failed: bool = True) -> dict:
        """Recover a document stuck in processing state."""
        report = {
            "document_id": document_id,
            "actions": [],
            "vectors_found": 0,
            "sections_found": 0,
            "promoted_to_ready": False,
            "marked_failed": False,
        }

        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            report["actions"].append("document_not_found")
            return report

        if doc["status"] != "processing":
            report["actions"].append(f"not_in_processing_state (status={doc['status']})")
            return report

        vector_count = await self.vector_store.count(document_id)
        report["vectors_found"] = vector_count

        section_count = await self.section_repo.count_by_document(document_id)
        report["sections_found"] = section_count

        if vector_count > 0 or section_count > 0:
            if vector_count > 0:
                if not mark_failed:
                    await self.doc_repo.update_status(
                        document_id,
                        status="ready",
                        stage="ready",
                        progress_percent=100,
                        status_message="Recovered from partial processing.",
                    )
                    report["promoted_to_ready"] = True
                    report["actions"].append(f"promoted_to_ready (vectors={vector_count})")
                else:
                    await self.doc_repo.update_status(
                        document_id,
                        status="failed",
                        stage="failed",
                        progress_percent=100,
                        status_message="Stuck in processing, marked as failed for retry.",
                    )
                    report["marked_failed"] = True
                    report["actions"].append("marked_failed")
            else:
                await self.doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    progress_percent=100,
                    status_message="Stuck: sections exist but no vectors. Marked failed.",
                )
                report["marked_failed"] = True
                report["actions"].append("marked_failed_no_vectors")
        else:
            await self.doc_repo.update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=100,
                status_message="Stuck in processing with no data. Marked failed.",
            )
            report["marked_failed"] = True
            report["actions"].append("marked_failed_no_data")

        return report

    async def check_orphaned_vectors(self, document_id: str) -> list[str]:
        """Find vector IDs that exist in Qdrant but have no corresponding section in PostgreSQL."""
        orphaned = []
        try:
            vectors_data, _ = await self.vector_store.scroll(
                query_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
                with_payload=True,
                with_vector=False,
                limit=10000,
            )

            section_ids = await self.section_repo.get_section_ids_by_document(document_id)

            for point in vectors_data:
                payload = point.get("payload", {})
                section_id = (payload.get("metadata") or {}).get("section_id")
                if section_id and str(section_id) not in section_ids:
                    orphaned.append(point.get("id"))
        except Exception as e:
            logger.error("[%s] Failed to check orphaned vectors: %s", document_id, e)

        return orphaned

    async def cleanup_orphaned_vectors(self, document_id: str) -> dict:
        """Remove vectors that have no matching section in PostgreSQL."""
        report = {"document_id": document_id, "orphaned_count": 0, "cleaned": 0, "error": None}
        try:
            orphaned = await self.check_orphaned_vectors(document_id)
            report["orphaned_count"] = len(orphaned)
            if orphaned:
                for vec_id in orphaned:
                    try:
                        await self.vector_store.delete_by_ids([vec_id])
                        report["cleaned"] += 1
                    except Exception as e:
                        report["error"] = str(e)
        except Exception as e:
            report["error"] = str(e)

        return report

    async def validate_section_vector_consistency(self, document_id: str) -> dict:
        """Validate that vectors in Qdrant have matching sections in PostgreSQL."""
        report = {"document_id": document_id, "total_vectors": 0, "total_sections": 0, "consistent": True, "issues": []}
        try:
            vector_count = await self.vector_store.count(document_id)
            report["total_vectors"] = vector_count
            section_count = await self.section_repo.count_by_document(document_id)
            report["total_sections"] = section_count

            orphaned = await self.check_orphaned_vectors(document_id)
            if orphaned:
                report["consistent"] = False
                report["issues"].append(f"orphaned_vectors: {len(orphaned)}")
            if section_count > 0 and vector_count == 0:
                report["consistent"] = False
                report["issues"].append("sections_exist_but_no_vectors")
        except Exception as e:
            report["consistent"] = False
            report["issues"].append(f"validation_error: {str(e)}")

        return report

    async def idempotency_check(self, task_id: str) -> dict | None:
        """Check if a task has already been processed."""
        try:
            record = await self.registry.get_by_task_id(task_id)
            if record and record.status == "ready":
                return {
                    "already_processed": True,
                    "task_id": task_id,
                    "document_id": record.document_id,
                    "status": record.status,
                }
        except Exception:
            pass
        return None

    async def _find_stuck_documents(self, timeout_minutes: int = 30) -> list[str]:
        """Find documents stuck in 'processing' state via repository."""
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        return await self.doc_repo.find_stuck_documents(timeout_threshold)
