from __future__ import annotations

import asyncio
import logging
import json
from typing import Any, AsyncGenerator

import httpx

from app.adapters.ai.base import AIProvider
from app.core.config import settings


logger = logging.getLogger(__name__)


class GoogleAIProvider(AIProvider):
    """
    Google Gemini AI provider with retry logic and robust streaming.

    Features:
    - Automatic retry on rate limits (429) and server errors (5xx)
    - Exponential backoff for retries
    - Proper SSE stream parsing with error handling
    - Graceful handling of client disconnects
    - Connection pooling for better performance
    """

    def __init__(self) -> None:
        self.model = settings.google_model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.api_key = settings.google_api_key
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY must be configured when AI_PROVIDER=google")

        # Configure connection pooling for better performance
        self.limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20,
            keepalive_expiry=30.0,
        )

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """
        Non-streaming chat with retry logic.

        Retries on:
        - Rate limits (429): exponential backoff (1s, 2s)
        - Server errors (5xx): 1 retry with 1s delay
        - Timeouts: 1 retry

        Returns:
            dict with 'answer' and 'citations' keys
        """
        prompt = self._build_prompt(messages, kwargs)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        # Retry logic: up to 2 attempts with exponential backoff
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=60.0, limits=self.limits) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    answer = self._extract_text(data)
                    citations = kwargs.get("citations") or []
                    return {"answer": answer, "citations": citations}

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt == 0:
                    # Rate limited - wait and retry
                    logger.warning("Rate limited, retrying after backoff...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s
                    continue
                elif e.response.status_code >= 500:
                    # Server error - retry once
                    if attempt == 0:
                        logger.warning("Server error %s, retrying...", e.response.status_code)
                        await asyncio.sleep(1)
                        continue
                    raise RuntimeError(f"Google AI server error: {e.response.status_code}") from None
                else:
                    # Client error - don't retry
                    error_data = self._safe_json_parse(e.response)
                    error_msg = error_data.get("error", {}).get("message", str(e))
                    raise RuntimeError(f"Google AI request failed: {error_msg}") from None

            except httpx.TimeoutException:
                if attempt == 0:
                    logger.warning("Timeout on first attempt, retrying...")
                    continue
                raise RuntimeError("Google AI request timed out after 60s") from None

            except Exception as exc:
                logger.error("Google AI unexpected error: %s", exc, exc_info=True)
                raise RuntimeError(f"Google AI request failed: {exc}") from None

        # Should not reach here, but just in case
        raise RuntimeError("Google AI request failed after retries")

    async def refine_text(self, text: str, current_header: str | None = None) -> tuple[str, str | None]:
        """
        Refine text using Gemma-4 to fix OCR errors and detect headers.

        Args:
            text: Raw text to refine (often with OCR errors)
            current_header: Current section header (optional)

        Returns:
            Tuple of (cleaned_text, detected_header)
        """
        if not text or not text.strip():
            return text, current_header

        # Build refinement prompt
        prompt = (
            "You are a text refinement tool for documents. Your tasks:\n"
            "1. Fix common OCR errors (e.g., 'M Ụ C T I Ê U' → 'MỤC TIÊU')\n"
            "2. Normalize whitespace\n"
            "3. Detect if first line is a header/title\n\n"
            f"Text to refine:\n{text[:2000]}\n\n"
            "Return JSON: {\"cleaned_text\": \"...\", \"detected_header\": \"...\" or null}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,  # Low temp for consistency
                "maxOutputTokens": 512,
            },
        }

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0, limits=self.limits) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract JSON response
                response_text = self._extract_text(data)
                if not response_text:
                    return text, current_header

                # Parse JSON
                import json as json_lib
                try:
                    # Try to extract JSON from response (may have extra text)
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
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
        Yields chunks of text as they are generated.

        Handles:
        - Connection errors with retry
        - Timeout errors with retry
        - Malformed SSE data (skips invalid chunks)
        - Client disconnects (GeneratorExit)
        - Rate limits (429) with exponential backoff

        Yields:
            str: Text chunks from AI response
        """
        prompt = self._build_prompt(messages, kwargs)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"

        # Retry logic for streaming
        for attempt in range(2):
            client = None
            try:
                client = httpx.AsyncClient(timeout=60.0, limits=self.limits)
                response = await client.post(url, json=payload)
                response.raise_for_status()

                chunk_count = 0
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        # SSE format: data: {...}
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            data = json.loads(json_str)
                            text = self._extract_text(data)
                            if text:
                                chunk_count += 1
                                logger.debug("Yielding chunk #%d: %d chars", chunk_count, len(text))
                                yield text
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse SSE line: %s (line: %s)", e, line[:200])
                        continue
                    except Exception as e:
                        logger.warning("Error processing SSE chunk: %s", e)
                        continue

                # If we got here successfully, break out of retry loop
                return

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt == 0:
                    logger.warning("Streaming rate limited, retrying after backoff...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                elif e.response.status_code >= 500 and attempt == 0:
                    logger.warning("Streaming server error %s, retrying...", e.response.status_code)
                    await asyncio.sleep(1)
                    continue
                else:
                    raise RuntimeError(f"Google AI streaming failed: {e.response.status_code}") from None

            except httpx.TimeoutException:
                if attempt == 0:
                    logger.warning("Streaming timeout, retrying...")
                    continue
                raise RuntimeError("Google AI streaming timed out after 60s") from None

            except GeneratorExit:
                # Client disconnected
                logger.info("Client disconnected during streaming")
                raise

            except Exception as exc:
                raise RuntimeError(f"Google AI streaming request failed: {exc}") from None

            finally:
                if client:
                    await client.aclose()

        # Should not reach here
        raise RuntimeError("Google AI streaming failed after retries")

    def _build_prompt(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> str:
        """
        Build prompt from message history and context.
        Detects language (Vietnamese/English) and formats context with citations.
        """
        user_query = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                user_query = str(message.get("content", "")).strip()
                break

        if not user_query:
            return "Vui lòng đặt câu hỏi về tài liệu."

        # Detect language from query (simple heuristic)
        vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳỹỷỵĐđABCDEFGHIJKLMNOPQRSTUVWXYZ')
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
                "Bạn là trợ lý AI thông minh. Nhiệm vụ: Đọc TẤT CẢ tài liệu và trả lời câu hỏi.\n\n"
                "QUY TẮC:\n"
                "1. Đọc và TỔNG HỢP thông tin từ TẤT CẢ tài liệu\n"
                "2. Viết câu trả lời hoàn chỉnh, có logic, có cấu trúc\n"
                "3. Trả lời tự nhiên như đang trò chuyện\n"
                "4. KHÔNG cần trích dẫn số [1], [2] trong câu trả lời\n"
                "5. Đừng chỉ liệt kê, hãy PHÂN TÍCH và TỔNG HỢP\n"
                "6. Nếu nhiều tài liệu nói về cùng chủ đề, tổng hợp lại\n"
                f"7. Trả lời bằng TIẾNG VIỆT (người dùng hỏi tiếng Việt)\n"
                "8. TRƯỚC KHI TRẢ LỜI: Hãy suy luận và phân tích trong thẻ <thinking>...</thinking>\n"
                "9. SAU ĐÓ: Đưa ra câu trả lời cuối cùng bên ngoài thẻ thinking\n\n"
                f"CÂU HỎI:\n{user_query}\n\n"
                f"TÀI LIỆU THAM KHẢO:\n{context_text}\n\n"
                "YÊU CẦU: Viết câu trả lời chi tiết, có phân tích. "
                "BẮT BUỘC phải có thẻ <thinking> trước khi trả lời."
            )
        else:
            return (
                "You are an intelligent AI assistant. Task: Read ALL documents and answer questions.\n\n"
                "RULES:\n"
                "1. Read and SYNTHESIZE information from ALL documents\n"
                "2. Write complete, logical, structured answers\n"
                "3. Answer naturally like in a conversation\n"
                "4. NO need for citations [1], [2] in the answer\n"
                "5. Don't just list, ANALYZE and SYNTHESIZE\n"
                "6. If multiple documents cover same topic, combine them\n"
                f"7. Answer in the same language as the question\n"
                "8. BEFORE ANSWERING: Think and reason inside <thinking>...</thinking> tags\n"
                "9. AFTER: Provide your final answer outside the thinking tags\n\n"
                f"QUESTION:\n{user_query}\n\n"
                f"REFERENCE DOCUMENTS:\n{context_text}\n\n"
                "REQUIREMENT: Write detailed, analytical answers. "
                "MUST include <thinking> tags before your final answer."
            )

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """
        Extract text from Google AI response.
        Handles various response formats and errors gracefully.
        """
        try:
            candidates = data.get("candidates") or []
            for candidate in candidates:
                content = candidate.get("content") or {}
                parts = content.get("parts") or []
                for part in parts:
                    text = part.get("text")
                    if text and text.strip():
                        return text.strip()

            # Check for finishReason to detect safety blocks
            if candidates:
                finish_reason = candidates[0].get("finishReason", "")
                if finish_reason == "SAFETY":
                    return "Nội dung này không được phép tạo ra do chính sách an toàn."

            return "Không thể tạo câu trả lời từ model Google ở thời điểm này."

        except Exception as e:
            logger.warning("Error extracting text from AI response: %s", e)
            return "Lỗi khi xử lý phản hồi từ AI."

    @staticmethod
    def _safe_json_parse(response: httpx.Response) -> dict[str, Any]:
        """Safely parse JSON from response, return empty dict on failure."""
        try:
            return response.json()
        except Exception:
            return {}
