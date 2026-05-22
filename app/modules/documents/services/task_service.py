import logging
import asyncio
from uuid import uuid4
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.modules.documents.repositories import DocumentRepository

logger = logging.getLogger(__name__)

TASK_TO_DOC_KEY = "task:doc:"


class TaskService:
    def __init__(self, doc_repo: DocumentRepository, redis_client=None):
        self.doc_repo = doc_repo
        self.redis = redis_client

    async def get_task_status(self, task_id: str) -> dict:
        try:
            if self.redis:
                raw = await self.redis.get(f"{TASK_TO_DOC_KEY}{task_id}")
                document_id = raw.decode("utf-8") if raw else None
            else:
                document_id = None
        except Exception:
            document_id = None

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
        task_id = str(uuid4())
        if self.redis:
            await self.redis.set(f"{TASK_TO_DOC_KEY}{task_id}", document_id)

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

        await asyncio.to_thread(
            celery_app.backend.store_result,
            task_id,
            {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
            state="QUEUED",
        )

        return task_id

    async def enqueue_rechunk(self, document_id: str, user_id: str) -> str:
        task_id = str(uuid4())
        if self.redis:
            await self.redis.set(f"{TASK_TO_DOC_KEY}{task_id}", document_id)

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
