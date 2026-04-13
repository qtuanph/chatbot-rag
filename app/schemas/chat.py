from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(max_length=5000)
    session_id: str | None = None
