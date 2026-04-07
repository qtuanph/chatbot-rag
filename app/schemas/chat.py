from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    stream: bool = True
