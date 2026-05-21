"""AI Proxy bridge — calls 9Router directly via HTTP (no LlamaIndex)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIProxyBridge:
    """Calls 9Router's OpenAI-compatible /v1/chat/completions endpoint directly.

    No LlamaIndex dependency — works with any model name 9Router knows.
    """

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        thinking_mode: bool = False,
    ):
        self.api_base = (api_base or settings.ai_proxy_url).rstrip("/")
        self.api_key = api_key or settings.ai_proxy_api_key
        self.model = model or settings.ai_proxy_default_model or ""
        self.thinking_mode = thinking_mode
        self.temperature = temperature if temperature is not None else settings.ai_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.ai_max_output_tokens
        self.last_usage: dict[str, Any] = {}

    @property
    def model_name(self) -> str:
        return self.model or "unknown"

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        full = ""
        async for chunk in self.chat_stream(messages, **kwargs):
            full += chunk
        return {
            "answer": full or "Không thể tạo câu trả lời lúc này. Vui lòng thử lại.",
            "citations": kwargs.get("citations") or [],
        }

    async def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Stream chat chunks via direct HTTP call to 9Router."""
        system_text = _SYSTEM_INSTRUCTION
        if mems := kwargs.get("user_memories"):
            system_text += f"\n\n## CÁ NHÂN HÓA\n{mems}\nƯu tiên áp dụng các ghi nhớ này."

        context = kwargs.get("context") or []
        formatted_context = kwargs.get("formatted_context") or ""
        query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        full_context = ""
        if formatted_context:
            full_context = formatted_context
        elif context:
            blocks = "\n\n".join(
                f"**{c.get('document_title', 'Tài liệu')} — {c.get('heading', 'Nội dung')}**"
                f"{' (trang ' + str(c.get('page_range', '')) + ')' if c.get('page_range') else ''}\n"
                f"{c.get('full_text', c.get('text', ''))}"
                for c in context
            )
            full_context = f"Tài liệu tham khảo:\n{blocks}\n---"

        user_query = f"{full_context}\nCâu hỏi: {query}" if full_context else query

        lm_messages = [{"role": "system", "content": system_text}]
        # Only include recent history (last N messages) to reduce prefill latency
        max_history = getattr(settings, "ai_max_history_messages", 10)
        history_to_send = messages[:-1][-max_history:] if len(messages) > 1 else messages[:-1]
        for msg in history_to_send:
            if msg.get("content"):
                lm_messages.append({"role": msg["role"], "content": msg["content"]})
        lm_messages.append({"role": "user", "content": user_query})

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": lm_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if self.thinking_mode:
            body["reasoning_effort"] = "high"

        url = f"{self.api_base}/v1/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=settings.ai_proxy_timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code != 200:
                        err_body = await resp.aread()
                        raise RuntimeError(f"9Router returned {resp.status_code}: {err_body.decode(errors='replace')}")

                    usage_info = {}
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices") or []
                        for c in choices:
                            delta = c.get("delta") or {}
                            if content := delta.get("content"):
                                yield content

                        if usage := chunk.get("usage"):
                            usage_info = usage

                    if usage_info:
                        self.last_usage = {
                            "prompt_tokens": usage_info.get("prompt_tokens", 0),
                            "completion_tokens": usage_info.get("completion_tokens", 0),
                            "total_tokens": usage_info.get("total_tokens", 0),
                        }

        except Exception as e:
            err_str = str(e).lower()
            logger.error("AI Proxy stream failed: %s", e, exc_info=True)

            if any(
                kw in err_str
                for kw in ("no client", "no provider", "no available", "0 clients", "no model", "no backend")
            ):
                yield (
                    "⚠️ **Hệ thống chưa sẵn sàng.**\n\n"
                    "Các nhân viên hỗ trợ AI hiện chưa được kết nối. "
                    "Vui lòng liên hệ Admin để cấu hình nhà cung cấp AI."
                )
            elif any(kw in err_str for kw in ("rate limit", "rate_limit", "429", "too many requests", "quota")):
                yield (
                    "⏳ **Nhân viên hỗ trợ đang bận.**\n\n"
                    "Hệ thống đang xử lý nhiều yêu cầu cùng lúc. "
                    "Vui lòng thử lại sau ít phút."
                )
            elif any(kw in err_str for kw in ("connection", "timeout", "connect error", "unreachable")):
                yield (
                    "🔌 **Không thể kết nối đến nhân viên hỗ trợ.**\n\n"
                    "Vui lòng thử lại sau. Nếu lỗi tiếp tục, hãy liên hệ Admin."
                )
            else:
                yield (
                    "❌ **Nhân viên hỗ trợ hiện không phản hồi.**\n\n"
                    "Vui lòng thử lại sau ít phút hoặc liên hệ Admin nếu lỗi tiếp tục."
                )

    async def refine_text(self, text: str, current_header: str | None = None, **kwargs: Any) -> tuple[str, str | None]:
        return text, current_header


_SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý AI chuyên nghiệp, trả lời câu hỏi dựa trên tài liệu được cung cấp.\n\n"
    "## QUY TẮC BẮT BUỘC\n"
    "1. Trả lời DUY NHẤT dựa trên nội dung trong phần 'Tài liệu tham khảo'. "
    "Không dùng kiến thức bên ngoài, không suy diễn, không bịa đặt.\n"
    "2. Nếu tài liệu không có thông tin để trả lời, nói rõ: "
    "'Tài liệu hiện tại chưa có thông tin về vấn đề này.' "
    "Không được tạo câu trả lời thay thế.\n"
    "3. BỎ QUA các metadata như: tên file, số trang, header/footer, "
    "'Hướng dẫn sử dụng', 'SSE., JSC.', 'trang X/Y'. Chỉ lấy nội dung chính.\n"
    "4. Đọc kỹ tài liệu, rút ra các Ý CHÍNH, rồi VIẾT LẠI bằng lời tự nhiên — "
    "như đang giải thích cho đồng nghiệp hiểu.\n"
    "5. KHÔNG copy-paste nguyên văn đoạn dài. KHÔNG liệt kê lại mục lục.\n"
    "6. KHÔNG lặp lại cùng 1 ý nhiều lần. Mỗi ý chỉ nói 1 lần, rõ ràng.\n"
    "7. KHÔNG bịa ra danh sách, bước, hoặc thông tin không có trong tài liệu.\n"
    "8. Nếu có nhiều nguồn, kết hợp thông tin thành câu trả lời thống nhất.\n"
    "9. Ưu tiên trả lời trực tiếp câu hỏi trước, sau đó giải thích chi tiết.\n\n"
    "## ĐỊNH DẠNG TRẢ LỜI\n"
    "- Mở đầu: Trả lời trực tiếp câu hỏi (1-2 câu).\n"
    "- Thân bài: Các ý chính dưới dạng gạch đầu dòng hoặc đoạn ngắn.\n"
    "- Dùng **in đậm** cho thuật ngữ quan trọng.\n"
    "- Giữ ngắn gọn — chỉ nêu thông tin thực sự liên quan đến câu hỏi.\n\n"
    "## GIỌNG ĐIỆU\n"
    "- Thân thiện, chuyên nghiệp, dễ hiểu.\n"
    "- Tiếng Việt tự nhiên, không dịch word-by-word.\n\n"
    "## LƯU Ý QUAN TRỌNG\n"
    "- KHÔNG thêm metadata (tên file, số trang, tên chương) vào câu trả lời.\n"
    "- KHÔNG nói 'theo tài liệu', 'trong tài liệu có viết' — trả lời trực tiếp như đang biết.\n"
    "- Nếu không có tài liệu tham khảo nào được cung cấp, "
    "hướng dẫn người dùng liên hệ Admin để được hỗ trợ."
)
