from __future__ import annotations

from pydantic import BaseModel, Field


class OpenAIMessage(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=20000)


class ChatCompletionsRequest(BaseModel):
    model: str | None = None
    messages: list[OpenAIMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    metadata: dict[str, str | int | float | bool | None] | None = None
