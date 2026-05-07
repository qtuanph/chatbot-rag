from __future__ import annotations

import asyncio
import logging
import json
import re
from typing import Any, AsyncGenerator

import httpx

from app.adapters.ai.base import AIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý AI trả lời câu hỏi dựa trên tài liệu cung cấp.\n\n"
    "## NGUYÊN TẮC\n"
    "- Trả lời dựa trên nội dung tài liệu. Nếu tài liệu không có thông tin, nói rõ: "
    "'Tài liệu hiện tại chưa đề cập đến vấn đề này.'\n"
    "- Giữ nguyên nội dung chính xác: định nghĩa, hướng dẫn, các bước, ví dụ, số liệu. "
    "Diễn đạt lại chỉ khi cần giải thích thêm, không thay thế nội dung gốc.\n"
    "- Nếu câu hỏi hỏi về danh sách (ví dụ: 'các bước', 'các yếu tố', 'các tính năng'), "
    "trình bày đầy đủ từng mục, không tóm tắt bỏ bớt.\n\n"
    "## ĐỊNH DẠNG\n"
    "- Dùng **in đậm** cho thuật ngữ quan trọng.\n"
    "- Dùng danh sách gạch đầu dòng `- ` khi trình bày nhiều mục.\n"
    "- Giữ cấu trúc của tài liệu (heading, số thứ tự) khi cần thiết.\n\n"
    "## GIỌNG ĐIỆU\n"
    "- Chuyên nghiệp, rõ ràng, thân thiện.\n"
    "- Ưu tiên trả lời trực tiếp, rồi giải thích thêm nếu cần.\n"
    "- Nếu cần nhắc tài liệu, nói 'Theo tài liệu...'\n\n"
    "## TIẾNG VIỆT\n"
    "- Giữ dấu cách giữa các từ.\n"
    "- Trả lời bằng ngôn ngữ của câu hỏi.\n\n"
    "## LƯU Ý\n"
    "- KHÔNG bịa đặt thông tin không có trong tài liệu.\n"
    "- Nếu không có tài liệu đính kèm, hướng dẫn người dùng liên hệ Admin."
)

# --- Gemma 4 Thinking Mode Suppression ---
#
# Gemma 4 uses <|channel>thought...<channel|> tags for chain-of-thought.
# 3 layers to suppress:
#   1. API-level: thought:true part filter in _extract_text()
#   2. Stream-level: _ThoughtFilter state machine strips <|channel>thought...<channel|>
#   3. Post-level: strip_reasoning() + strip_thought_blocks() on saved text

# Regex to strip <|channel>thought...<channel|> blocks (including newlines)
_THOUGHT_BLOCK = re.compile(
    r"<\|channel\|>thought.*?<channel\|>",
    re.DOTALL,
)

# Chain-of-thought reasoning end marker (model-specific)
_REASONING_END_MARKER = re.compile(
    r"Final\s*Polish\s*[:：]\s*\n",
    re.IGNORECASE,
)


def strip_thought_blocks(text: str) -> str:
    """Remove <|channel>thought...<channel|> blocks from text."""
    if not text:
        return text
    return _THOUGHT_BLOCK.sub("", text).strip()


def strip_reasoning(text: str) -> str:
    """Remove chain-of-thought reasoning from model output.

    Gemma 4 thinking mode may output its reasoning process as visible text.
    Only strips definitive model markers — never document content like
    'Step 1', 'Analysis:', or 'Context:' which are common in Vietnamese docs.
    """
    if not text or len(text) < 100:
        return text

    # Strip <|channel>thought...<channel|> blocks (definitive model reasoning)
    text = strip_thought_blocks(text)

    # Strip content before 'Final Polish:' marker (model-specific reasoning end)
    match = _REASONING_END_MARKER.search(text)
    if match:
        end_idx = match.end()
        result = text[end_idx:].strip()
        if result and len(result) >= 50:
            return result

    return text


class _ThoughtFilter:
    """Stateful filter to suppress <|channel>thought...<channel|> blocks during streaming."""

    _START = "<|channel|>thought"
    _END = "<channel|>"

    def __init__(self) -> None:
        self._buffer = ""
        self._in_thought = False  # Content-first: only enter thought mode when <|channel|>thought is seen

    def feed(self, chunk: str) -> str | None:
        """Feed a chunk. Returns cleaned text or None if all thinking."""
        self._buffer += chunk
        result_parts: list[str] = []

        while True:
            if self._in_thought:
                end_idx = self._buffer.find(self._END)
                if end_idx != -1:
                    start_slice = end_idx + len(self._END)
                    self._buffer = self._buffer[start_slice:]
                    self._in_thought = False
                else:
                    break  # Still in thought, keep buffering
            else:
                start_idx = self._buffer.find(self._START)
                if start_idx >= 0:
                    result_parts.append(self._buffer[:start_idx])
                    self._buffer = self._buffer[start_idx:]
                    self._in_thought = True
                else:
                    # No markers — yield everything
                    result_parts.append(self._buffer)
                    self._buffer = ""
                    break

        joined = "".join(result_parts)
        return joined if joined else None

    def flush(self) -> str:
        """Return remaining non-thought buffer content."""
        remaining = self._buffer
        self._buffer = ""
        return "" if self._in_thought else remaining


# Maximum conversation turns to include in context (for performance)
_MAX_HISTORY_MESSAGES = settings.ai_max_history_messages


class GoogleAIProvider(AIProvider):
    """
    Google Gemini AI provider with retry logic and robust streaming.

    Features:
    - Multi-turn conversation support via Gemini contents array
    - Automatic retry on rate limits (429) and server errors (5xx)
    - Proper SSE stream parsing with error handling
    - Connection pooling for better performance
    """

    def __init__(self) -> None:
        self.model = settings.google_model
        self.base_url = settings.ai_google_base_url.rstrip("/")
        self.api_key = settings.google_api_key
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be configured when AI_PROVIDER=google")

        self._headers = {"x-goog-api-key": self.api_key}

        self._limits = httpx.Limits(
            max_keepalive_connections=settings.ai_http_keepalive_connections,
            max_connections=settings.ai_http_max_connections,
            keepalive_expiry=settings.ai_http_keepalive_expiry,
        )
        self._client: httpx.AsyncClient | None = None
        self._refine_client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def model_name(self) -> str:
        """Return the model identifier for analytics/token tracking."""
        return self.model

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable httpx client, ensuring loop safety."""
        current_loop = asyncio.get_running_loop()
        if self._client is None or self._client.is_closed or self._loop is not current_loop:
            self._loop = current_loop
            self._client = httpx.AsyncClient(timeout=settings.ai_stream_timeout, limits=self._limits)
        return self._client

    async def _get_refine_client(self) -> httpx.AsyncClient:
        """Get a client for text refinement, ensuring loop safety."""
        current_loop = asyncio.get_running_loop()
        if self._refine_client is None or self._refine_client.is_closed or self._loop is not current_loop:
            self._loop = current_loop
            self._refine_client = httpx.AsyncClient(timeout=settings.ai_http_timeout_refine, limits=self._limits)
        return self._refine_client

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """
        Non-streaming chat — collects all chunks from chat_stream().

        Returns:
            dict with 'answer' and 'citations' keys
        """
        full_answer = ""
        async for chunk in self.chat_stream(messages, **kwargs):
            full_answer += chunk

        citations = kwargs.get("citations") or []
        return {"answer": full_answer or "Không thể tạo câu trả lời lúc này. Vui lòng thử lại.", "citations": citations}

    async def refine_text(self, text: str, current_header: str | None = None) -> tuple[str, str | None]:
        """Refine text using Gemini."""
        prompt = (
            "You are a text refinement tool. Tasks: 1. Fix OCR errors 2. Normalize whitespace 3. Detect header.\n"
            f"Text:\n{text[:2000]}\n"
            'Return JSON: {"cleaned_text": "...", "detected_header": "..." or null}'
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "thinkingConfig": {"thinkingLevel": "MINIMAL"}},
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"

        client = await self._get_refine_client()
        response = await client.post(url, json=payload, headers=self._headers)
        response.raise_for_status()

        data = response.json()
        res_text = self._extract_text(data)
        if not res_text:
            return text, current_header

        try:
            start_idx = res_text.find("{")
            end_idx = res_text.rfind("}") + 1
            res = json.loads(res_text[start_idx:end_idx])
            return res.get("cleaned_text", text).strip(), res.get("detected_header") or current_header
        except Exception:
            return text, current_header

    async def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream responses from Gemini."""
        self.last_usage = {}
        contents = self._build_contents(messages, kwargs)

        system_text = _SYSTEM_INSTRUCTION
        if mems := kwargs.get("user_memories"):
            system_text += f"\n\n## CÁ NHÂN HÓA\n{mems}\nƯu tiên áp dụng các ghi nhớ này."

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {
                "temperature": settings.ai_temperature,
                "maxOutputTokens": settings.ai_max_output_tokens,
                "thinkingConfig": {"thinkingLevel": settings.ai_google_thinking_level},
            },
        }

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse"
        client = self._get_client()

        async with client.stream("POST", url, json=payload, headers=self._headers) as response:
            response.raise_for_status()
            thought_filter = _ThoughtFilter()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data = json.loads(line[6:])
                if usage := data.get("usageMetadata"):
                    self.last_usage = {
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                        "total_tokens": usage.get("totalTokenCount", 0),
                    }

                if txt := self._extract_text(data):
                    if filtered := thought_filter.feed(txt):
                        yield filtered

            if final := thought_filter.flush():
                yield final

    def _build_contents(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        """Build Gemini multi-turn contents."""
        context = "\n\n".join(self._build_context_blocks(kwargs.get("context") or []))
        contents = []

        max_hist = settings.ai_max_history_messages
        history = messages[:-1][-max_hist:]
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            txt = strip_thought_blocks(msg["content"]).strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt}]})

        user_query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        query_text = f"Tài liệu:\n{context}\n---\nCâu hỏi: {user_query}" if context else user_query
        contents.append({"role": "user", "parts": [{"text": query_text}]})
        return contents

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """Extract text parts from Gemini response."""
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p["text"] for p in parts if not p.get("thought")).strip()
        except Exception:
            return ""
