from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Generate a chat response."""
        raise NotImplementedError

    async def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any):
        """
        Stream chat response chunks. Default implementation yields full response.

        Override this method in subclasses for true streaming support.
        """
        response = await self.chat(messages, **kwargs)
        yield response.get("answer", "")

    async def refine_text(self, text: str, current_header: str | None = None, **kwargs: Any) -> tuple[str, str | None]:
        """
        Refine text content (e.g., fix OCR errors, improve readability).
        Returns tuple of (cleaned_text, detected_header).

        Default implementation returns text unchanged.
        """
        return text, current_header
