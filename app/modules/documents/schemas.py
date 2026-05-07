from pydantic import BaseModel, Field


class UploadAcceptedResponse(BaseModel):
    task_id: str
    status: str
    document_id: str


class TaskProgressInfo(BaseModel):
    step: str
    percent: int


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    stage: str | None = None
    progress: TaskProgressInfo
    document_id: str | None = None
    status_message: str | None = None
    error: str | None = None
    result: dict[str, object] | None = None


class DocumentDeleteResponse(BaseModel):
    status: str
    document_id: str


class DocumentSummaryResponse(BaseModel):
    document_id: str
    title: str
    file_name: str
    file_type: str
    file_size: int
    version: int
    status: str
    stage: str
    progress_percent: int
    status_message: str | None = None
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    offset: int = 0
    limit: int = Field(default=20, ge=1, le=100)


class DocumentRetryResponse(BaseModel):
    task_id: str
    document_id: str
    status: str


class DocumentDetailResponse(BaseModel):
    document_id: str
    title: str
    file_name: str
    sha256: str
    file_type: str
    file_size: int
    version: int
    status: str
    stage: str
    progress_percent: int
    status_message: str | None = None
    parse_error: str | None = None
    artifact_metadata: dict[str, object]
    deleted_at: str | None = None
    created_at: str
    updated_at: str
