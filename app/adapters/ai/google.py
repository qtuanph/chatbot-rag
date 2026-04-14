from __future__ import annotations

import itertools
from typing import Any

import httpx

from app.adapters.ai.base import AIProvider
from app.core.config import settings


class GoogleAIProvider(AIProvider):
    def __init__(self) -> None:
        self.model = settings.google_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.api_keys = settings.get_google_api_keys()
        if not self.api_keys:
            raise ValueError("GOOGLE_API_KEY or GOOGLE_API_KEYS must be configured when AI_PROVIDER=google")
        self._key_cycle = itertools.cycle(self.api_keys)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        prompt = self._build_prompt(messages, kwargs)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        last_error: Exception | None = None
        for _ in range(len(self.api_keys)):
            api_key = next(self._key_cycle)
            url = f"{self.base_url}/models/{self.model}:generateContent?key={api_key}"
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(url, json=payload)

                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = RuntimeError(f"Google AI temporary error: {response.status_code}")
                    continue
                response.raise_for_status()
                data = response.json()
                answer = self._extract_text(data)
                citations = kwargs.get("citations") or []
                return {"answer": answer, "citations": citations}
            except Exception as exc:
                last_error = exc
                continue

        if last_error:
            raise RuntimeError(f"Google AI request failed after trying all keys: {last_error}")
        raise RuntimeError("Google AI request failed unexpectedly")

    def _build_prompt(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> str:
        user_query = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_query = str(message.get("content", "")).strip()
                break

        # Detect language from query (simple heuristic)
        vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỹỷỵABCDEFGHIJKLMNOPQRSTUVWXYZ')
        is_vietnamese = any(char in vietnamese_chars for char in user_query)

        context_nodes = kwargs.get("context") or []

        # Build rich context with inline citation markers
        context_blocks: list[str] = []
        for idx, node in enumerate(context_nodes, start=1):
            title = node.get("document_title") or "Untitled"
            heading = node.get("heading") or "Section"
            text = (node.get("full_text") or "")[:2000]  # Balanced context
            context_blocks.append(f"[{idx}] {title} | {heading}\n{text}")

        context_text = "\n\n".join(context_blocks) if context_blocks else "NO DOCUMENTS"

        if is_vietnamese:
            return (
                "Bạn là trợ lý AI thông minh. Nhiệm vụ: TỔNG HỢP thông tin từ TẤT CẢ tài liệu để trả lời câu hỏi.\n\n"
                "QUY TẮC:\n"
                "1. Đọc TẤT CẢ các nguồn được đánh dấu [1], [2], [3]...\n"
                "2. TỔNG HỢP thông tin từ nhiều nguồn khác nhau\n"
                "3. Viết câu trả lời hoàn chỉnh, có logic, có cấu trúc\n"
                "4. Khi trích dẫn, dùng format [1], [2] trong câu trả lời\n"
                "5. Đừng chỉ liệt kê, hãy PHÂN TÍCH và TỔNG HỢP\n"
                "6. Nếu nhiều tài liệu nói về cùng chủ đề, tổng hợp lại\n"
                f"7. Trả lời bằng TIẾNG VIỆT (người dùng hỏi tiếng Việt)\n\n"
                f"CÂU HỎI:\n{user_query}\n\n"
                f"TÀI LIỆU THAM KHẢO:\n{context_text}\n\n"
                "YÊU CẦU: Viết câu trả lời chi tiết, có phân tích, có trích dẫn."
            )
        else:
            return (
                "You are an intelligent AI assistant. Task: SYNTHESIZE information from ALL documents to answer questions.\n\n"
                "RULES:\n"
                "1. Read ALL sources marked [1], [2], [3]...\n"
                "2. SYNTHESIZE information from multiple different sources\n"
                "3. Write complete, logical, structured answers\n"
                "4. Use citation format [1], [2] within answers\n"
                "5. Don't just list, ANALYZE and SYNTHESIZE\n"
                "6. If multiple documents cover same topic, combine them\n"
                f"7. Answer in the same language as the question\n\n"
                f"QUESTION:\n{user_query}\n\n"
                f"REFERENCE DOCUMENTS:\n{context_text}\n\n"
                "REQUIREMENT: Write detailed, analytical answers with citations."
            )

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                text = part.get("text")
                if text and text.strip():
                    return text.strip()
        return "Không thể tạo câu trả lời từ model Google ở thời điểm này."
