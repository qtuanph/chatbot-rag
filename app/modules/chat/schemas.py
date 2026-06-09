from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatCitationPayload(BaseModel):
    document_id: str
    section_id: str | None = None
    file_name: str | None = None
    title: str | None = None
    heading: str | None = None
    page_range: str | None = None
    score: float | None = None


class ChatFeedbackRequest(BaseModel):
    tenant_id: str | None = None
    feedback_type: Literal["like", "dislike"]
    query_text: str = Field(min_length=1, max_length=10_000)
    assistant_answer: str = Field(min_length=1, max_length=40_000)
    citations: list[ChatCitationPayload] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatFeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str | None = None
    feedback_type: Literal["like", "dislike"]
    created_at: str
