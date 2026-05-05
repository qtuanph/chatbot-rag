"""Documents API — upload, status, list, delete, retry."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.api.deps import AuthContext, get_document_service, require_admin
from app.core.config import settings
from app.core import http_errors
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentRetryResponse,
    DocumentSummaryResponse,
    TaskProgressInfo,
    TaskStatusResponse,
    UploadAcceptedResponse,
)
from app.utils.throttle import RequestThrottle
from app.services.documents.document_service import DocumentService

router = APIRouter(tags=["documents"])
throttle = RequestThrottle()


@router.post("/upload", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
) -> UploadAcceptedResponse:
    if not throttle.allow(
        f"throttle:upload:{auth.user_id}", limit=settings.effective_rate_limit(5), window_seconds=300
    ):
        raise http_errors.too_many_requests("Too many upload requests")

    if not file.filename:
        raise http_errors.bad_request("Filename is required")
    if len(file.filename) > settings.max_filename_length:
        raise http_errors.bad_request(f"Filename exceeds maximum length of {settings.max_filename_length} characters")
    if "/" in file.filename or "\\" in file.filename or ".." in file.filename or "\x00" in file.filename:
        raise http_errors.bad_request("Filename contains invalid path characters")

    file_type = file.content_type or "application/octet-stream"
    allowed_types = settings.get_allowed_file_types()
    if file_type not in allowed_types:
        raise http_errors.bad_request(
            f"File type '{file_type}' is not allowed. Allowed types: {', '.join(sorted(allowed_types))}"
        )

    max_size = settings.max_upload_size_mb * 1024 * 1024

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_size:
                raise http_errors.payload_too_large(f"File size exceeds maximum of {settings.max_upload_size_mb} MB")
        except ValueError:
            pass

    # Stream-read file in chunks to avoid memory exhaustion on large files
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise http_errors.payload_too_large(f"File size exceeds maximum of {settings.max_upload_size_mb} MB")
        chunks.append(chunk)
    content = b"".join(chunks) if chunks else b""
    if total_size == 0:
        raise http_errors.bad_request("File cannot be empty")

    # Delegate to service for duplicate check, storage, DB insert, and task enqueue
    from uuid import uuid4

    document_id = str(uuid4())
    duplicate, next_version, sha256 = await service.check_duplicate(content, file.filename)
    if duplicate is not None:
        raise http_errors.conflict("Document already exists")

    task_id = await service.create_and_enqueue(
        document_id=document_id,
        filename=file.filename,
        content=content,
        file_type=file_type,
        sha256=sha256,
        next_version=next_version,
        user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return UploadAcceptedResponse(task_id=task_id, status="queued", document_id=document_id)


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(
    task_id: str, _auth=Depends(require_admin), service: DocumentService = Depends(get_document_service)
) -> TaskStatusResponse:
    if not throttle.allow(
        f"throttle:status:{_auth.user_id}", limit=settings.effective_rate_limit(60), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many status requests")

    result = await service.get_task_status(task_id)
    return TaskStatusResponse(
        task_id=result["task_id"],
        status=result["status"],
        stage=result["stage"],
        progress=TaskProgressInfo(step=result["stage"], percent=result["percent"]),
        document_id=result["document_id"],
        status_message=result["status_message"],
        error=result["error"],
        result=result["result"],
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    offset: int = 0,
    limit: int = 20,
    _auth=Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    offset = max(0, offset)
    limit = max(1, min(limit, 100))
    if not throttle.allow(
        f"throttle:documents:{_auth.user_id}", limit=settings.effective_rate_limit(30), window_seconds=60
    ):
        raise http_errors.too_many_requests("Too many document list requests")

    result = await service.list_documents(offset=offset, limit=limit)
    items = [
        DocumentSummaryResponse(
            document_id=row["document_id"],
            title=row["title"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            file_size=row["file_size"],
            version=row["version"],
            status=row["status"],
            stage=row["stage"],
            progress_percent=row["progress_percent"],
            status_message=row["status_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result["items"]
    ]
    return DocumentListResponse(items=items, total=result["total"], offset=result["offset"], limit=result["limit"])


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: str, _auth=Depends(require_admin), service: DocumentService = Depends(get_document_service)
) -> DocumentDetailResponse:
    try:
        doc = await service.get_document_detail(document_id)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
    return DocumentDetailResponse(
        document_id=doc["id"],
        title=doc["title"],
        file_name=doc["file_name"],
        sha256=doc["sha256"],
        file_type=doc["file_type"],
        file_size=doc["file_size"],
        version=doc["version"],
        status=doc["status"],
        stage=doc["status_stage"],
        progress_percent=doc["progress_percent"],
        status_message=doc["status_message"],
        parse_error=doc["parse_error"],
        metadata=doc["artifact_metadata"],
        deleted_at=doc["deleted_at"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    request: Request,
    document_id: str,
    _auth=Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
) -> DocumentDeleteResponse:
    try:
        result = await service.delete_document(
            document_id=document_id,
            user_id=_auth.user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return DocumentDeleteResponse(**result)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
    except RuntimeError as e:
        raise http_errors.service_unavailable(str(e)) from None


@router.post("/documents/{document_id}/retry", response_model=DocumentRetryResponse)
async def retry_document(
    request: Request,
    document_id: str,
    auth: AuthContext = Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
) -> DocumentRetryResponse:
    try:
        result = await service.retry_document(
            document_id=document_id,
            user_id=auth.user_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return DocumentRetryResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        raise http_errors.bad_request(msg) from None
    except RuntimeError as e:
        raise http_errors.service_unavailable(str(e)) from None
