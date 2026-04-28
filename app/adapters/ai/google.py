from __future__ import annotations

import asyncio
import logging
import json
import random
import re
from typing import Any, AsyncGenerator

import httpx

from app.adapters.ai.base import AIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    # ── Identity ──
    "Bạn là trợ lý AI thân thiện cho hệ thống hỏi đáp tài liệu tiếng Việt.\n"
    "Bạn đọc tài liệu tham khảo, HIỂU nội dung, rồi kể lại bằng giọng điệu tự nhiên như đang nói chuyện.\n\n"
    # ── Style ──
    "## PHONG CÁCH\n"
    "- Nói chuyện tự nhiên, thân thiện, như đang trả lời bạn bè.\n"
    "- KHÔNG dùng số thứ tự tham chiếu như [1], [2], [3].\n"
    "- KHÔNG cần liệt kê nguồn ở cuối câu trả lời.\n"
    "- Nếu cần nhắc tài liệu, chỉ nói 'Theo giáo trình...' hoặc 'Tài liệu có đề cập đến...'\n"
    "- Tóm tắt ngắn gọn. Ưu tiên trả lời trực tiếp câu hỏi.\n\n"
    # ── Vietnamese rules ──
    "## TIẾNG VIỆT\n"
    "- LUÔN giữ dấu cách giữa các từ: 'tài liệu' KHÔNG 'tàiliệu'\n"
    "- LUÔN có space sau # heading: `## Tiêu đề` (KHÔNG `##Tiêu đề`)\n"
    "- Dùng `**in đậm**` cho thuật ngữ, `- ` cho danh sách khi cần.\n\n"
    # ── Content rules ──
    "## NỘI DUNG\n"
    "- TỔNG HỢP và DIỄN GIẢI lại bằng lời văn của bạn. KHÔNG copy nguyên văn.\n"
    "- Nếu tài liệu không đủ thông tin, nói: 'Tài liệu hiện tại chưa đề cập đến vấn đề này...'\n"
    "- KHÔNG bịa đặt. KHÔNG dùng heading cấp 1.\n\n"
    # ── Few-shot example ──
    "## VÍ DỤ\n"
    "User: SEO là gì?\n"
    "Assistant: SEO (Search Engine Optimization) là quá trình tối ưu hóa nội dung và cấu trúc "
    "trang web để cải thiện vị trí hiển thị trên công cụ tìm kiếm như Google. "
    "Tài liệu nhấn mạnh rằng SEO bao gồm 3 yếu tố chính: **nghiên cứu từ khóa**, "
    "**tối ưu nội dung** và **xây dựng liên kết**. Mục tiêu là thu hút lưu lượng truy cập "
    "tự nhiên mà không cần trả phí cho quảng cáo.\n\n"
    # ── Meta ──
    "## LƯU Ý\n"
    "- Trả lời bằng ngôn ngữ của câu hỏi.\n"
    "- Nếu không có tài liệu, hướng dẫn người dùng liên hệ Admin."
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

# Chain-of-thought reasoning markers (fallback for non-tagged CoT)
_REASONING_END_MARKER = re.compile(
    r"Final\s*Polish\s*[:：]\s*\n",
    re.IGNORECASE,
)

_REASONING_LINE_MARKER = re.compile(
    r"^\s*(?:"
    r"Question\s*[:：]|"
    r"Source\s*Material\s*[:：]|"
    r"Document\s*\[\d+\]\s*[:：]|"
    r"Definition\s*[:：]|"
    r"Context\s*[:：]|"
    r"Objectives?\s*[:：]|"
    r"Heading\s*[:：]|"
    r"Structure\s*[:：]|"
    r"Drafting|"
    r"Self[-\s]Correction|"
    r"Final\s*Polish\s*[:：]|"
    r"Analysis\s*[:：]|"
    r"Planning\s*[:：]|"
    r"Step\s+\d+"
    r")",
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
    This function strips that reasoning and returns only the final answer.
    """
    if not text or len(text) < 100:
        return text

    # First: strip <|channel>thought...<channel|> blocks
    text = strip_thought_blocks(text)

    # Then: strip reasoning markers
    match = _REASONING_END_MARKER.search(text)
    if match:
        result = text[match.end() :].strip()
        if result and len(result) >= 50:
            return result

    lines = text.split("\n")
    cleaned = [line for line in lines if not _REASONING_LINE_MARKER.match(line)]
    result = "\n".join(cleaned).strip()

    if len(result) < len(text) * 0.3:
        return text

    return result


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
                if end_idx >= 0:
                    self._buffer = self._buffer[end_idx + len(self._END) :]
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
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.api_key = settings.google_api_key
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be configured when AI_PROVIDER=google")

        self._headers = {"x-goog-api-key": self.api_key}

        self._limits = httpx.Limits(
            max_keepalive_connections=settings.ai_http_keepalive_connections,
            max_connections=settings.ai_http_max_connections,
            keepalive_expiry=30.0,
        )
        self._client: httpx.AsyncClient | None = None

    @property
    def model_name(self) -> str:
        """Return the model identifier for analytics/token tracking."""
        return self.model

    def _get_client(self, timeout: float | None = None) -> httpx.AsyncClient:
        """Get or create a reusable httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=timeout or settings.ai_stream_timeout, limits=self._limits)
        return self._client

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
        """
        Refine text using Gemini to fix OCR errors and detect headers.
        """
        if not text or not text.strip():
            return text, current_header

        prompt = (
            "You are a text refinement tool for documents. Your tasks:\n"
            "1. Fix common OCR errors (e.g., 'M Ụ C T I Ê U' → 'MỤC TIÊU')\n"
            "2. Normalize whitespace\n"
            "3. Detect if first line is a header/title\n\n"
            f"Text to refine:\n{text[:2000]}\n\n"
            'Return JSON: {"cleaned_text": "...", "detected_header": "..." or null}'
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 512,
                "thinkingConfig": {"thinkingLevel": "MINIMAL"},
            },
        }

        url = f"{self.base_url}/models/{self.model}:generateContent"

        try:
            client = self._get_client(timeout=30.0)
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()

            response_text = self._extract_text(data)
            if not response_text:
                return text, current_header

            import json as json_lib

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    result = json_lib.loads(json_str)
                    cleaned = result.get("cleaned_text", text).strip()
                    header = result.get("detected_header") or current_header
                    return cleaned, header
            except Exception as e:
                logger.warning("Failed to parse refinement JSON: %s", e)
                return text, current_header

        except Exception as e:
            logger.warning("Text refinement failed, using fallback: %s", e)
            return text, current_header

    async def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
        """
        Stream chat responses from Google Gemini API.
        Uses multi-turn contents array for conversation history support.

        After streaming completes, token usage is available via `self.last_usage`.
        """
        self.last_usage: dict[str, int] = {}
        contents = self._build_contents(messages, kwargs)

        # Build system instruction with optional user memories
        system_text = _SYSTEM_INSTRUCTION
        user_memories = kwargs.get("user_memories", "")
        if user_memories:
            # Inject memories as a dedicated section within the prompt structure
            system_text = f"{_SYSTEM_INSTRUCTION}\n\n## CÁ NHÂN HÓA\n{user_memories}\nHãy ưu tiên áp dụng các ghi nhớ này khi trả lời."

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {
                "temperature": settings.ai_temperature,
                "maxOutputTokens": settings.ai_max_output_tokens,
                "thinkingConfig": {"thinkingLevel": "MINIMAL"},
            },
        }

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse"

        for attempt in range(3):
            try:
                client = self._get_client()

                async with client.stream("POST", url, json=payload, headers=self._headers) as response:
                    response.raise_for_status()

                    chunk_count = 0
                    thought_filter = _ThoughtFilter()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            if line.startswith("data: "):
                                json_str = line[6:]
                                data = json.loads(json_str)

                                usage = data.get("usageMetadata")
                                if usage:
                                    self.last_usage = {
                                        "prompt_tokens": usage.get("promptTokenCount", 0),
                                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                                        "total_tokens": usage.get("totalTokenCount", 0),
                                    }

                                text = self._extract_text(data)
                                if text:
                                    filtered = thought_filter.feed(text)
                                    if filtered:
                                        chunk_count += 1
                                        yield filtered
                        except json.JSONDecodeError as e:
                            logger.warning("Failed to parse SSE line: %s (line: %s)", e, line[:200])
                            continue
                        except Exception as e:
                            logger.warning("Error processing SSE chunk: %s", e)
                            continue

                    remaining = thought_filter.flush()
                    if remaining:
                        chunk_count += 1
                        yield remaining

                return

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    backoff = min(2**attempt + random.uniform(0, 1), 10)
                    logger.warning("Streaming rate limited, retrying in %.1fs...", backoff)
                    await asyncio.sleep(backoff)
                    continue
                elif e.response.status_code >= 500 and attempt < 2:
                    logger.warning("Streaming server error %s, retrying...", e.response.status_code)
                    await asyncio.sleep(1)
                    continue
                else:
                    raise RuntimeError(f"Google AI streaming failed: {e.response.status_code}") from None

            except httpx.TimeoutException:
                if attempt < 2:
                    logger.warning("Streaming timeout, retrying...")
                    continue
                raise RuntimeError("Google AI streaming timed out after 300s") from None

            except GeneratorExit:
                logger.info("Client disconnected during streaming")
                raise

            except Exception as exc:
                raise RuntimeError(f"Google AI streaming request failed: {exc}") from None

        raise RuntimeError("Google AI streaming failed after retries")

    def _build_contents(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        """Build Gemini-format multi-turn contents array.

        Converts conversation history into Gemini's expected format:
        [{"role": "user", "parts": [{"text": "..."}]},
         {"role": "model", "parts": [{"text": "..."}]},
         ...]

        The RAG context is embedded into the current (last) user message.
        """
        context_nodes = kwargs.get("context") or []
        context_blocks = self._build_context_blocks(context_nodes)
        context_text = "\n\n".join(context_blocks) if context_blocks else ""

        contents: list[dict[str, Any]] = []

        # Previous conversation history (all messages except the last one)
        history = messages[:-1] if messages else []
        # Limit to last N messages for performance
        if len(history) > _MAX_HISTORY_MESSAGES:
            history = history[-_MAX_HISTORY_MESSAGES:]

        for msg in history:
            role = "model" if msg.get("role") == "assistant" else "user"
            content = str(msg.get("content", "")).strip()
            # Strip thought blocks from previous assistant responses
            # to prevent model from continuing thinking mode
            if role == "model":
                content = strip_thought_blocks(content)
            if content:
                contents.append({"role": role, "parts": [{"text": content}]})

        # Build current user message with RAG context
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = str(msg.get("content", "")).strip()
                break

        if not user_query:
            return [{"role": "user", "parts": [{"text": "Vui lòng đặt câu hỏi."}]}]

        if context_text:
            current_text = (
                f"Dựa vào tài liệu sau để trả lời câu hỏi. "
                f"Chỉ sử dụng thông tin từ tài liệu, không bịa đặt.\n\n"
                f"{context_text}\n\n"
                f"---\nCâu hỏi: {user_query}"
            )
        else:
            current_text = user_query

        contents.append({"role": "user", "parts": [{"text": current_text}]})

        return contents

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """Extract text from Google AI response, skipping thinking parts."""
        try:
            candidates = data.get("candidates") or []
            for candidate in candidates:
                content = candidate.get("content") or {}
                parts = content.get("parts") or []
                for part in parts:
                    # Skip thinking/reasoning parts (Gemma 4 thinking mode)
                    if part.get("thought"):
                        continue
                    text = part.get("text")
                    if text and text.strip():
                        return text.strip()
            return ""
        except Exception:
            return ""
