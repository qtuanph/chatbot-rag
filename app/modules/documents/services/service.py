"""Document service — upload, status, delete, retry business logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from app.adapters.storage import build_storage
from app.core.celery_app import celery_app
from app.modules.documents.repositories import DocumentRepository, SectionRepository
from app.modules.documents.services import TaskService, TreeService
from app.modules.documents.utils.document_registry import DocumentRegistry
from app.utils.audit import safe_record_audit

logger = logging.getLogger(__name__)


class DocumentService:
    """Business logic for document metadata and lifecycle management."""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        section_repo: SectionRepository,
        registry: DocumentRegistry,
        task_service: TaskService | None = None,
        tree_service: TreeService | None = None,
    ) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.registry = registry
        self.task_service = task_service or TaskService(doc_repo, registry)
        self.tree_service = tree_service or TreeService(doc_repo, section_repo)

        from app.modules.documents.utils import DuplicateDetector

        self.detector = DuplicateDetector(registry.client)

    # ── Status ──────────────────────────────────────────────────────

    async def get_task_status(self, task_id: str) -> dict:
        """Delegated to TaskService."""
        return await self.task_service.get_task_status(task_id)

    # ── Upload ──────────────────────────────────────────────────────

    async def check_duplicate(self, sha256: str, filename: str) -> tuple[dict | None, int]:
        """Check SHA256 duplicate + get next version. Returns (duplicate_doc, next_version)."""
        if not await self.detector.exists(sha256):
            next_version = await self.doc_repo.get_next_version(filename)
            return None, next_version

        duplicate = await self.doc_repo.find_by_sha256(sha256)
        next_version = await self.doc_repo.get_next_version(filename)
        return duplicate, next_version

    async def create_and_enqueue(
        self,
        *,
        document_id: str,
        filename: str,
        fileobj: Any,
        file_size: int,
        file_type: str,
        sha256: str,
        next_version: int,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Create document record and delegate enqueuing to TaskService."""
        storage = build_storage()
        object_uri = await asyncio.to_thread(
            storage.save_fileobj, document_id=document_id, filename=filename, fileobj=fileobj
        )

        await self.doc_repo.insert_document(
            document_id=document_id,
            title=filename,
            file_name=filename,
            file_path=object_uri,
            sha256=sha256,
            file_type=file_type,
            file_size=file_size,
            version=next_version,
        )

        await self.detector.add(sha256)

        safe_record_audit(
            action="document.upload",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"filename": filename, "size": file_size, "file_type": file_type},
            redis_client_override=self.registry.client,
        )

        try:
            task_id = await self.task_service.enqueue_ingestion(
                document_id=document_id, object_uri=object_uri, filename=filename, user_id=user_id
            )
            await self.doc_repo.update_status(
                document_id,
                status="pending",
                stage="queued",
                progress_percent=5,
                status_message="Task queued for worker processing.",
            )
            return task_id
        except Exception as exc:
            logger.error("Failed to enqueue document task for %s: %s", document_id, exc, exc_info=True)
            await self.registry.purge_async(document_id)
            await self.doc_repo.soft_delete(document_id)
            if hasattr(storage, "delete_object"):
                await asyncio.to_thread(storage.delete_object, object_uri)
            raise RuntimeError("Failed to enqueue document task. Please try again later.") from exc

    # ── List / Detail ───────────────────────────────────────────────

    async def list_documents(self, offset: int = 0, limit: int = 20) -> dict:
        items, total = await self.doc_repo.list_paginated(offset=offset, limit=limit)
        return {
            "items": [
                {
                    "document_id": row["id"],
                    "title": row["title"],
                    "file_name": row["file_name"],
                    "file_type": row["file_type"],
                    "file_size": row["file_size"],
                    "version": row["version"],
                    "status": row["status"],
                    "stage": row["status_stage"],
                    "progress_percent": row["progress_percent"],
                    "status_message": row["status_message"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in items
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    async def get_document_detail(self, document_id: str) -> dict:
        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            raise ValueError("Document not found")
        return doc

    async def get_document_tree(self, document_id: str) -> list:
        """Delegated to TreeService."""
        return await self.tree_service.get_document_tree(document_id)

    # ── Delete ──────────────────────────────────────────────────────

    async def delete_document(
        self, *, document_id: str, user_id: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> dict:
        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            raise ValueError("Document not found")

        await self.registry.delete(document_id)
        await self.doc_repo.mark_as_deleted(document_id)

        delete_task_id = str(uuid4())
        try:
            await asyncio.to_thread(
                celery_app.send_task,
                "app.workers.cleanup_tasks.delete_document_task",
                kwargs={
                    "task_id": delete_task_id,
                    "document_id": document_id,
                    "user_id": user_id,
                },
                task_id=delete_task_id,
            )
            await asyncio.to_thread(
                celery_app.backend.store_result,
                delete_task_id,
                {
                    "stage": "delete_queued",
                    "progress": {"step": "delete_queued", "percent": 0},
                    "document_id": document_id,
                },
                state="QUEUED",
            )
        except Exception as exc:
            logger.error("Failed to enqueue delete task for %s: %s", document_id, exc, exc_info=True)
            raise RuntimeError("Failed to enqueue delete task. Please try again later.") from exc

        safe_record_audit(
            action="document.delete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"status": "deleted", "task_id": delete_task_id},
            redis_client_override=self.registry.client,
        )

        return {"status": "deleted", "document_id": document_id}

    # ── Retry ───────────────────────────────────────────────────────

    async def retry_document(
        self, *, document_id: str, user_id: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> dict:
        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            raise ValueError("Document not found")
        if doc["status"] != "failed":
            raise ValueError("Only failed documents can be retried")

        file_path = doc["file_path"]
        filename = doc["file_name"]

        # Cleanup artifacts via repos
        try:
            from app.adapters.vector_stores import build_vector_store

            vector_store = await build_vector_store()
            await vector_store.delete(document_id)
            await self.section_repo.delete_sections(document_id)
        except Exception as exc:
            logger.warning("Retry: partial cleanup failed for document %s: %s", document_id, exc)

        await self.doc_repo.reset_for_retry(document_id)

        try:
            new_task_id = await self.task_service.enqueue_ingestion(
                document_id=document_id, object_uri=file_path, filename=filename, user_id=user_id
            )
        except Exception as exc:
            logger.error("Retry: failed to enqueue task for document %s: %s", document_id, exc)
            await self.doc_repo.update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=100,
                status_message="Retry failed: could not enqueue task.",
            )
            raise RuntimeError("Failed to enqueue retry task.") from exc

        safe_record_audit(
            action="document.retry",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"task_id": new_task_id},
            redis_client_override=self.registry.client,
        )

        return {"task_id": new_task_id, "document_id": document_id, "status": "queued"}
