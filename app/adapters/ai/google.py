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

        context_nodes = kwargs.get("context") or []
        context_blocks: list[str] = []
        for idx, node in enumerate(context_nodes, start=1):
            title = node.get("document_title") or "Untitled"
            heading = node.get("heading") or "Section"
            text = (node.get("full_text") or "")[:2000]
            context_blocks.append(f"[{idx}] {title} | {heading}\n{text}")

        context_text = "\n\n".join(context_blocks) if context_blocks else "No document context available."

        return (
            "You are an enterprise AI assistant. Your primary task is to answer questions STRICTLY based on the provided document context.\n"
            "CRITICAL RULES:\n"
            "1. If the user sends a simple greeting (e.g. hello, xin chào), respond naturally and politely, but briefly remind them that you are ready to answer questions based on the enterprise documents uploaded by the Admin.\n"
            "2. If the user asks a factual question and the context is empty ('No document context available.'), you MUST NOT hallucinate or answer from outside knowledge. Instead, explicitly answer: 'Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống.'\n"
            "3. If the context has documents but they don't contain the answer, say you don't know based on the current documents.\n"
            "4. Always respond in Vietnamese.\n\n"
            f"User question:\n{user_query}\n\n"
            f"Context:\n{context_text}\n"
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
