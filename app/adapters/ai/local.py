from __future__ import annotations

from typing import Any

from app.adapters.ai.base import AIProvider


class LocalAIProvider(AIProvider):
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        query = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                query = str(message.get("content", ""))
                break
        context = kwargs.get("context") or []
        citations = kwargs.get("citations") or []
        if not context:
            return {
                "answer": "Chưa có dữ liệu tài liệu phù hợp để trả lời.",
                "citations": [],
            }
        context_blocks = self._build_context_blocks(context, max_context_chars=6000)
        context_text = "\n\n".join(context_blocks)
        return {
            "answer": (
                f"Dựa trên tài liệu đã index, câu hỏi '{query}' có liên quan đến {len(context)} đoạn nội dung.\n\n"
                f"Trích đoạn tham chiếu:\n{context_text}"
            ),
            "citations": citations,
        }

    async def refine_text(self, text: str, current_header: str | None = None, **kwargs: Any) -> tuple[str, str | None]:
        """Local fallback: return text unchanged."""
        return text, current_header
