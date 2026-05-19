import logging
import asyncio
from uuid import uuid4
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.modules.documents.repositories import DocumentRepository
from app.modules.documents.utils.document_registry import DocumentRecord, DocumentRegistry

logger = logging.getLogger(__name__)


class TaskService:
    """Specialized service for managing background task lifecycle and status."""

    def __init__(self, doc_repo: DocumentRepository, registry: DocumentRegistry):
        self.doc_repo = doc_repo
        self.registry = registry

    async def get_task_status(self, task_id: str) -> dict:
        """Merge status from DB (primary) + Celery (secondary) for granular tracking."""
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
                "error": document.get("parse_error"),
                "result": document.get("artifact_metadata", {}).get("ingestion_artifact"),
            }

        # Fallback to Celery if DB record is not yet in sync
        def _get_celery_info():
            res = AsyncResult(task_id, app=celery_app)
            return {
                "state": res.state.lower(),
                "info": res.info if isinstance(res.info, dict) else {},
                "failed": res.failed(),
                "result": res.result if res.successful() else None,
            }

        r = await asyncio.to_thread(_get_celery_info)
        return {
            "task_id": task_id,
            "status": r["state"],
            "stage": str(r["info"].get("stage") or r["state"]),
            "percent": r["info"].get("progress", {}).get("percent", 0),
            "document_id": document_id or r["info"].get("document_id"),
            "status_message": "Task initializing or in queue...",
            "error": str(r["result"]) if r["failed"] else None,
            "result": r["result"] if not r["failed"] else None,
        }

    async def enqueue_ingestion(self, document_id: str, object_uri: str, filename: str, user_id: str) -> str:
        """Enqueue a new ingestion task."""
        task_id = str(uuid4())
        await self.registry.put(
            DocumentRecord(
                document_id=document_id,
                task_id=task_id,
                object_uri=object_uri,
                filename=filename,
                status="queued",
            )
        )

        await asyncio.to_thread(
            celery_app.send_task,
            "app.workers.upload_tasks.parse_document_task",
            kwargs={
                "task_id": task_id,
                "document_id": document_id,
                "file_path": object_uri,
                "user_id": user_id,
            },
            task_id=task_id,
        )

        # Initial status in Celery backend
        await asyncio.to_thread(
            celery_app.backend.store_result,
            task_id,
            {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
            state="QUEUED",
        )

        return task_id

    async def enqueue_rechunk(self, document_id: str, user_id: str) -> str:
        """Enqueue a rechunk task that re-indexes from saved OCR markdown."""
        task_id = str(uuid4())
        await self.registry.put(
            DocumentRecord(
                document_id=document_id,
                task_id=task_id,
                object_uri="",
                filename="",
                status="queued",
            )
        )

        await asyncio.to_thread(
            celery_app.send_task,
            "app.workers.upload_tasks.rechunk_document_task",
            kwargs={
                "task_id": task_id,
                "document_id": document_id,
                "user_id": user_id,
            },
            task_id=task_id,
        )

        await asyncio.to_thread(
            celery_app.backend.store_result,
            task_id,
            {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
            state="QUEUED",
        )

        return task_id
