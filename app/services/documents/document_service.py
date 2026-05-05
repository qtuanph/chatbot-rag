"""Document service — upload, status, delete, retry business logic."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from uuid import uuid4

from celery.result import AsyncResult

from app.adapters.storage import build_storage
from app.core.celery_app import celery_app
from app.repositories.document_repository import DocumentRepository
from app.repositories.section_repository import SectionRepository
from app.utils.document_registry import DocumentRecord, DocumentRegistry
from app.utils.audit import safe_record_audit

logger = logging.getLogger(__name__)


class DocumentService:
    """Business logic for document upload, status, delete, and retry."""

    def __init__(
        self, doc_repo: DocumentRepository, section_repo: SectionRepository, registry: DocumentRegistry
    ) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.registry = registry
        from app.utils.duplicate_detector import DuplicateDetector

        self.detector = DuplicateDetector(registry.client)

    # ── Upload ──────────────────────────────────────────────────────

    async def check_duplicate(self, content: bytes, filename: str) -> tuple[dict | None, int, str]:
        """Check SHA256 duplicate + get next version. Returns (duplicate_doc, next_version)."""
        sha256 = hashlib.sha256(content).hexdigest()

        # 1. Fast check via Bloom Filter (O(1) skip DB)
        if not await self.detector.exists(sha256):
            next_version = await self.doc_repo.get_next_version(filename)
            return None, next_version, sha256

        # 2. Potential duplicate: verify with DB
        duplicate = await self.doc_repo.find_by_sha256(sha256)
        next_version = await self.doc_repo.get_next_version(filename)
        return duplicate, next_version, sha256

    async def create_and_enqueue(
        self,
        *,
        document_id: str,
        filename: str,
        content: bytes,
        file_type: str,
        sha256: str,
        next_version: int,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Create document record, save to storage, enqueue Celery task. Returns task_id."""
        storage = build_storage()

        # Storage is currently sync in this codebase (Disk/S3 wrappers)
        # We use thread for CPU/IO bound sync storage call to not block event loop
        import asyncio

        object_uri = await asyncio.to_thread(
            storage.save_bytes, document_id=document_id, filename=filename, content=content
        )

        await self.doc_repo.insert_document(
            document_id=document_id,
            title=filename,
            file_name=filename,
            file_path=object_uri,
            sha256=sha256,
            file_type=file_type,
            file_size=len(content),
            version=next_version,
        )

        # Add to Bloom filter for future duplicate checks
        await self.detector.add(sha256)

        await safe_record_audit(
            action="document.upload",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"filename": filename, "size": len(content), "file_type": file_type},
        )

        task_id = str(uuid4())
        try:
            await self.registry.put(
                DocumentRecord(
                    document_id=document_id,
                    task_id=task_id,
                    object_uri=object_uri,
                    filename=filename,
                    status="queued",
                )
            )
            # Celery send_task is fast but we can use thread to be safe
            await asyncio.to_thread(
                celery_app.send_task,
                "app.workers.upload_tasks.parse_document_task",
                kwargs={
                    "task_id": task_id,
                    "document_id": document_id,
                    "file_path": object_uri,
                },
                task_id=task_id,
            )
            await asyncio.to_thread(
                celery_app.backend.store_result,
                task_id,
                {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
                state="QUEUED",
            )
            await self.doc_repo.update_status(
                document_id,
                status="pending",
                stage="queued",
                progress_percent=5,
                status_message="Task queued for worker processing.",
            )
        except Exception as exc:
            logger.error("Failed to enqueue document task for %s: %s", document_id, exc, exc_info=True)
            await self.registry.purge_async(document_id)
            await self.doc_repo.soft_delete(document_id)
            if hasattr(storage, "delete_object"):
                await asyncio.to_thread(storage.delete_object, object_uri)
            raise RuntimeError("Failed to enqueue document task. Please try again later.") from exc

        return task_id

    # ── Status ──────────────────────────────────────────────────────

    async def get_task_status(self, task_id: str) -> dict:
        """Merge status from DB (primary) + Celery (secondary)."""
        record = await self.registry.get_by_task_id(task_id)
        document_id = record.document_id if record else None
        document = await self.doc_repo.get_full_document(document_id) if document_id else None

        if document:
            return {
                "task_id": task_id,
                "status": document["status"],
                "stage": document.get("status_stage"),
                "percent": int(document["progress_percent"]),
                "document_id": document_id,
                "status_message": document.get("status_message"),
                "error": None,
                "result": None,
            }

        # Fallback to Celery if DB record not yet created or stuck
        def _get_result():
            result = AsyncResult(task_id, app=celery_app)
            return {
                "state": result.state.lower(),
                "info": result.info if isinstance(result.info, dict) else {},
                "failed": result.failed(),
                "result": result.result if result.successful() else None,
            }

        r = await asyncio.to_thread(_get_result)
        state = r["state"]
        info = r["info"]

        return {
            "task_id": task_id,
            "status": state,
            "stage": str(info.get("stage") or state),
            "percent": info.get("progress", {}).get("percent", 0),
            "document_id": document_id or info.get("document_id"),
            "status_message": "Task in queue or initializing...",
            "error": str(r["result"]) if r["failed"] else None,
            "result": r["result"] if not r["failed"] else None,
        }

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

    # ── Delete ──────────────────────────────────────────────────────

    async def delete_document(
        self, *, document_id: str, user_id: str, ip_address: str | None = None, user_agent: str | None = None
    ) -> dict:
        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            raise ValueError("Document not found")

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

        await safe_record_audit(
            action="document.delete",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"status": "delete_queued", "task_id": delete_task_id},
        )

        return {"status": "delete_queued", "document_id": document_id}

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

        # Clean up partial artifacts (vectors + sections)
        try:
            from app.adapters.vector_stores import build_vector_store

            vector_store = build_vector_store()
            try:
                await vector_store.delete(document_id)
                logger.info("Retry: deleted vectors for document %s", document_id)
            except Exception:
                logger.warning("Retry: no vectors to delete for document %s", document_id, exc_info=True)

            await self.section_repo.delete_sections(document_id)
        except Exception as exc:
            logger.warning("Retry: partial cleanup failed for document %s: %s", document_id, exc, exc_info=True)

        # Reset status
        new_task_id = str(uuid4())
        await self.doc_repo.reset_for_retry(document_id)

        # Re-queue ingestion task
        try:
            await self.registry.put(
                DocumentRecord(
                    document_id=document_id,
                    task_id=new_task_id,
                    object_uri=file_path,
                    filename=filename,
                    status="queued",
                )
            )
            await asyncio.to_thread(
                celery_app.send_task,
                "app.workers.upload_tasks.parse_document_task",
                kwargs={
                    "task_id": new_task_id,
                    "document_id": document_id,
                    "file_path": file_path,
                },
                task_id=new_task_id,
            )
            await asyncio.to_thread(
                celery_app.backend.store_result,
                new_task_id,
                {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
                state="QUEUED",
            )
        except Exception as exc:
            logger.error("Retry: failed to enqueue task for document %s: %s", document_id, exc, exc_info=True)
            await self.doc_repo.update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=100,
                status_message="Retry failed: could not enqueue task.",
            )
            raise RuntimeError("Failed to enqueue retry task. Please try again later.") from exc

        await safe_record_audit(
            action="document.retry",
            actor_user_id=user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"task_id": new_task_id},
        )

        return {"task_id": new_task_id, "document_id": document_id, "status": "queued"}
