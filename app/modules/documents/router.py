"""Documents API — upload, status, list, delete, retry, tree."""

from __future__ import annotations


from fastapi import APIRouter, Depends, File, Request, UploadFile, status, Query
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.utils.rate_limiter import RateLimiter

from app.api.deps import (
    AuthContext,
    get_document_service,
    require_admin,
    get_rate_limiter,
    get_tree_service,
    get_auth_context,
)
from app.core.config import settings
from app.core import http_errors
from app.modules.documents.schemas import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentRetryResponse,
    DocumentSummaryResponse,
    TaskProgressInfo,
    TaskStatusResponse,
    UploadAcceptedResponse,
)
from app.modules.documents.services import DocumentService, TreeService
from app.modules.documents.validators import DocumentValidator

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> UploadAcceptedResponse:
    if not await rate_limiter.is_allowed(
        f"upload:{auth.user_id}", limit=settings.effective_rate_limit(5), window_ms=300000
    ):
        raise http_errors.too_many_requests("Too many upload requests")

    try:
        filename = DocumentValidator.validate_filename(file.filename)
        file_type = DocumentValidator.validate_file_type(file.content_type)
    except ValueError as e:
        raise http_errors.bad_request(str(e)) from None

    import hashlib

    sha256_hash = hashlib.sha256()
    total_size = 0

    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total_size += len(chunk)
        try:
            DocumentValidator.validate_size(total_size)
        except ValueError as e:
            raise http_errors.bad_request(str(e)) from None
        except RuntimeError as e:
            raise http_errors.payload_too_large(str(e)) from None

        sha256_hash.update(chunk)

    sha256 = sha256_hash.hexdigest()
    await file.seek(0)

    from uuid import uuid4

    document_id = str(uuid4())

    duplicate, next_version = await service.check_duplicate(sha256, filename)
    if duplicate is not None:
        raise http_errors.conflict("Document already exists")

    task_id = await service.create_and_enqueue(
        document_id=document_id,
        filename=filename,
        fileobj=file.file,
        file_size=total_size,
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
    task_id: str,
    _auth=Depends(require_admin),
    service: DocumentService = Depends(get_document_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> TaskStatusResponse:
    if not await rate_limiter.is_allowed(
        f"status:{_auth.user_id}", limit=settings.effective_rate_limit(60), window_ms=60000
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
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> DocumentListResponse:
    offset = max(0, offset)
    limit = max(1, min(limit, 100))
    if not await rate_limiter.is_allowed(
        f"documents:{_auth.user_id}", limit=settings.effective_rate_limit(30), window_ms=60000
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
        artifact_metadata=doc["artifact_metadata"],
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


# ── Tree & Hierarchy Endpoints ──


@router.get("/tree/{document_id}")
async def get_document_tree(
    document_id: str,
    offset: int = 0,
    limit: int = 100,
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    if not await rate_limiter.is_allowed(
        f"tree:list:{auth.user_id}", limit=settings.effective_rate_limit(60), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many tree requests")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    try:
        return await service.get_document_tree(document_id=document_id, offset=offset, limit=limit)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None


@router.get("/tree/{document_id}/nodes/{node_id}")
async def get_node_details(
    document_id: str,
    node_id: str,
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    if not await rate_limiter.is_allowed(
        f"tree:detail:{auth.user_id}", limit=settings.effective_rate_limit(120), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many node detail requests")
    try:
        return await service.get_node_details(document_id=document_id, node_id=node_id)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None


@router.get("/tree/{document_id}/search")
async def search_nodes(
    document_id: str,
    query: str = Query(..., min_length=1, max_length=500),
    auth: AuthContext = Depends(get_auth_context),
    service: TreeService = Depends(get_tree_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    if not await rate_limiter.is_allowed(
        f"tree:search:{auth.user_id}", limit=settings.effective_rate_limit(60), window_ms=60000
    ):
        raise http_errors.too_many_requests("Too many tree search requests")
    try:
        return await service.search_nodes(document_id=document_id, query=query)
    except ValueError as e:
        raise http_errors.not_found(str(e)) from None
