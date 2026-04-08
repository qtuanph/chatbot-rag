from uuid import uuid4
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from celery.result import AsyncResult

from app.api.deps import AuthContext, get_auth_context, require_admin
from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.core import Document, DocNode
from app.db.session import SessionLocal
from app.schemas.documents import UploadAcceptedResponse
from app.services.registry import DocumentRecord, DocumentRegistry
from app.services.storage import build_storage
from app.services.audit import safe_record_audit
from app.services.throttle import RequestThrottle


router = APIRouter(tags=["documents"])
registry = DocumentRegistry()
throttle = RequestThrottle()


@router.post("/upload", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(request: Request, file: UploadFile = File(...), auth: AuthContext = Depends(require_admin)) -> UploadAcceptedResponse:
    if not throttle.allow(f"throttle:upload:{auth.user_id}", limit=5, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many upload requests")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="File too large")

    document_id = str(uuid4())
    task_id = str(uuid4())
    sha256 = hashlib.sha256(content).hexdigest()
    storage = build_storage()
    object_uri = storage.save_bytes(document_id=document_id, filename=file.filename, content=content)

    with SessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                title=file.filename,
                file_name=file.filename,
                file_path=object_uri,
                sha256=sha256,
                file_type=file.content_type or "application/octet-stream",
                file_size=len(content),
                status="pending",
            )
        )
        session.commit()
        safe_record_audit(
            action="document.upload",
            actor_user_id=auth.user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"filename": file.filename, "size": len(content)},
        )

    try:
        registry.put(
            DocumentRecord(
                document_id=document_id,
                task_id=task_id,
                object_uri=object_uri,
                filename=file.filename,
                status="queued",
            )
        )
        celery_app.send_task(
            "app.worker.parse_document_task",
            kwargs={
                "task_id": task_id,
                "document_id": document_id,
                "file_path": object_uri,
            },
            task_id=task_id,
        )
        celery_app.backend.store_result(
            task_id,
            {"stage": "queued", "progress": {"step": "queued", "percent": 0}, "document_id": document_id},
            state="QUEUED",
        )
    except Exception as exc:
        with SessionLocal() as session:
            session.query(DocNode).filter(DocNode.document_id == document_id).delete(synchronize_session=False)
            document = session.get(Document, document_id)
            if document is not None:
                document.deleted_at = datetime.now(timezone.utc)
                document.status = "failed"
            session.commit()
        if hasattr(storage, "delete_object"):
            storage.delete_object(object_uri)
        raise HTTPException(status_code=503, detail=f"Failed to enqueue document task: {exc}") from exc

    return UploadAcceptedResponse(task_id=task_id, status="queued", document_id=document_id)


@router.get("/status/{task_id}")
async def get_status(task_id: str, _auth=Depends(get_auth_context)) -> dict[str, object]:
    record = registry.get_by_task_id(task_id)
    if record and record.deleted:
        return {
            "task_id": task_id,
            "status": "deleted",
            "progress": {"step": "deleted", "percent": 100},
            "document_id": record.document_id,
        }

    result = AsyncResult(task_id, app=celery_app)
    info = result.info if isinstance(result.info, dict) else {}

    if result.successful():
        payload = result.result if isinstance(result.result, dict) else {}
        if record:
            record.status = "ready"
            registry.update(record)
        return {
            "task_id": task_id,
            "status": "ready",
            "progress": {"step": "done", "percent": 100},
            "document_id": payload.get("document_id"),
            "result": payload,
        }
    if result.failed():
        if record:
            record.status = "failed"
            registry.update(record)
        return {
            "task_id": task_id,
            "status": "failed",
            "progress": {"step": "failed", "percent": 100},
            "error": str(result.result),
        }

    if record:
        return {
            "task_id": task_id,
            "status": record.status,
            "progress": info.get("progress", {"step": record.status, "percent": 0}),
            "stage": info.get("stage", record.status),
            "document_id": record.document_id,
        }

    return {
        "task_id": task_id,
        "status": result.state.lower(),
        "progress": info.get("progress", {"step": result.state.lower(), "percent": 0}),
        "stage": info.get("stage"),
        "document_id": info.get("document_id"),
    }


@router.delete("/documents/{document_id}")
async def soft_delete_document(request: Request, document_id: str, _auth=Depends(require_admin)) -> dict[str, str]:
    record = registry.get_by_document_id(document_id)
    storage = build_storage()
    if hasattr(storage, "delete_object"):
        if record:
            storage.delete_object(record.object_uri)

    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is not None:
            document.deleted_at = datetime.now(timezone.utc)
            document.status = "deleted"
            session.query(DocNode).filter(DocNode.document_id == document_id).delete(synchronize_session=False)
            session.commit()
        safe_record_audit(
            action="document.delete",
            actor_user_id=_auth.user_id,
            subject_type="document",
            subject_id=document_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"status": "deleted"},
        )

    if record:
        try:
            celery_app.backend.delete(record.task_id)
        except Exception:
            pass
        registry.delete(document_id)

    return {"status": "deleted", "document_id": document_id}
