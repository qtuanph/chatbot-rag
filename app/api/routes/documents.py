from uuid import uuid4
import hashlib
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from celery.result import AsyncResult
from sqlalchemy import func

from app.api.deps import AuthContext, require_admin
from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.core import Document
from app.db.session import SessionLocal
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    TaskProgressInfo,
    TaskStatusResponse,
    UploadAcceptedResponse,
)
from app.services.registry import DocumentRecord, DocumentRegistry
from app.services.storage import build_storage
from app.services.audit import safe_record_audit
from app.services.throttle import RequestThrottle


router = APIRouter(tags=["documents"])
registry = DocumentRegistry()
throttle = RequestThrottle()
logger = logging.getLogger(__name__)


def _to_status_response(
    *,
    task_id: str,
    status_value: str,
    stage: str,
    percent: int,
    document_id: str | None,
    status_message: str | None = None,
    error: str | None = None,
    result: dict[str, object] | None = None,
) -> TaskStatusResponse:
    return TaskStatusResponse(
        task_id=task_id,
        status=status_value,
        stage=stage,
        progress=TaskProgressInfo(step=stage, percent=percent),
        document_id=document_id,
        status_message=status_message,
        error=error,
        result=result,
    )


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

    with SessionLocal() as session:
        duplicate = (
            session.query(Document)
            .filter(Document.sha256 == sha256, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .first()
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail="Document already exists"
            )

        next_version = (
            session.query(func.coalesce(func.max(Document.version), 0))
            .filter(Document.file_name == file.filename, Document.deleted_at.is_(None))
            .scalar()
            + 1
        )

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
                version=next_version,
                status="pending",
                status_stage="uploaded",
                progress_percent=1,
                status_message="File uploaded and awaiting queue.",
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
            "app.workers.upload_pipeline.parse_document_task",
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
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.status = "pending"
                document.status_stage = "queued"
                document.progress_percent = 5
                document.status_message = "Task queued for worker processing."
                document.status_updated_at = datetime.now(timezone.utc)
                session.commit()
    except Exception as exc:
        logger.error(f"Failed to enqueue document task for {document_id}: {exc}", exc_info=True)
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            if document is not None:
                document.deleted_at = datetime.now(timezone.utc)
                document.status = "failed"
                document.status_stage = "enqueue_failed"
                document.progress_percent = 100
                document.status_message = "Failed to enqueue ingestion task."
                document.status_updated_at = datetime.now(timezone.utc)
            session.commit()
        if hasattr(storage, "delete_object"):
            storage.delete_object(object_uri)
        raise HTTPException(status_code=503, detail="Failed to enqueue document task. Please try again later.") from exc

    return UploadAcceptedResponse(task_id=task_id, status="queued", document_id=document_id)


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str, _auth=Depends(require_admin)) -> TaskStatusResponse:
    if not throttle.allow(f"throttle:status:{_auth.user_id}", limit=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many status requests")

    record = registry.get_by_task_id(task_id)
    if record and record.deleted:
        return _to_status_response(
            task_id=task_id,
            status_value="deleted",
            stage="deleted",
            percent=100,
            document_id=record.document_id,
            status_message="Document was deleted.",
        )

    result = AsyncResult(task_id, app=celery_app)
    info = result.info if isinstance(result.info, dict) else {}
    document_id = record.document_id if record else info.get("document_id")
    document = None
    if document_id:
        with SessionLocal() as session:
            document = session.get(Document, document_id)

    status_value = document.status if document is not None else (record.status if record else result.state.lower())
    stage = (
        document.status_stage
        if document is not None and document.status_stage
        else str(info.get("stage") or status_value)
    )
    percent = int(document.progress_percent if document is not None else info.get("progress", {}).get("percent", 0))
    status_message = document.status_message if document is not None else None

    if result.successful():
        payload = result.result if isinstance(result.result, dict) else {}
        if record:
            record.status = "ready"
            registry.update(record)
        payload_stage = str(payload.get("stage")) if payload.get("stage") else None
        payload_status = str(payload.get("status")) if payload.get("status") else None
        payload_percent = payload.get("progress", {}).get("percent") if isinstance(payload.get("progress"), dict) else None
        return _to_status_response(
            task_id=task_id,
            status_value=(payload_status or (document.status if document is not None else "ready")),
            stage=(payload_stage or (document.status_stage if document is not None and document.status_stage else "ready")),
            percent=(int(payload_percent) if payload_percent is not None else (int(document.progress_percent) if document is not None else 100)),
            document_id=payload.get("document_id") or document_id,
            status_message=document.status_message if document is not None else str(payload.get("status_message") or "Task complete."),
            result=payload,
        )
    if result.failed():
        if record:
            record.status = "failed"
            registry.update(record)
        return _to_status_response(
            task_id=task_id,
            status_value=(document.status if document is not None else "failed"),
            stage=(document.status_stage if document is not None and document.status_stage else "failed"),
            percent=(int(document.progress_percent) if document is not None else 100),
            document_id=document_id,
            status_message=document.status_message if document is not None else None,
            error=str(result.result),
        )

    return _to_status_response(
        task_id=task_id,
        status_value=status_value,
        stage=stage,
        percent=percent,
        document_id=document_id,
        status_message=status_message,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(_auth=Depends(require_admin)) -> DocumentListResponse:
    if not throttle.allow(f"throttle:documents:{_auth.user_id}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many document list requests")

    with SessionLocal() as session:
        rows = (
            session.query(Document)
            .filter(Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .all()
        )

    items = [
        DocumentSummaryResponse(
            document_id=str(row.id),
            title=row.title,
            file_name=row.file_name,
            file_type=row.file_type,
            file_size=row.file_size,
            version=row.version,
            status=row.status,
            stage=row.status_stage,
            progress_percent=int(row.progress_percent),
            status_message=row.status_message,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )
        for row in rows
    ]
    return DocumentListResponse(items=items, total=len(items))


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(document_id: str, _auth=Depends(require_admin)) -> DocumentDetailResponse:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentDetailResponse(
            document_id=str(document.id),
            title=document.title,
            file_name=document.file_name,
            file_path=document.file_path,
            sha256=document.sha256,
            file_type=document.file_type,
            file_size=document.file_size,
            version=document.version,
            status=document.status,
            stage=document.status_stage,
            progress_percent=int(document.progress_percent),
            status_message=document.status_message,
            parse_error=document.parse_error,
            metadata=dict(document.extra_metadata or {}),
            deleted_at=document.deleted_at.isoformat() if document.deleted_at else None,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(request: Request, document_id: str, _auth=Depends(require_admin)) -> DocumentDeleteResponse:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

    delete_task_id = str(uuid4())

    try:
        celery_app.send_task(
            "app.workers.cleanup_pipeline.delete_document_task",
            kwargs={
                "task_id": delete_task_id,
                "document_id": document_id,
                "user_id": _auth.user_id,
            },
            task_id=delete_task_id,
        )
        celery_app.backend.store_result(
            delete_task_id,
            {"stage": "delete_queued", "progress": {"step": "delete_queued", "percent": 0}, "document_id": document_id},
            state="QUEUED",
        )
    except Exception as exc:
        logger.error(f"Failed to enqueue delete task for {document_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to enqueue delete task. Please try again later.") from exc

    safe_record_audit(
        action="document.delete",
        actor_user_id=_auth.user_id,
        subject_type="document",
        subject_id=document_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"status": "delete_queued", "task_id": delete_task_id},
    )

    return DocumentDeleteResponse(status="delete_queued", document_id=document_id)
