from pydantic import BaseModel


class UploadAcceptedResponse(BaseModel):
    task_id: str
    status: str
    document_id: str
