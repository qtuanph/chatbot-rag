"""Context compaction for long conversations.

Auto-triggered when estimated history tokens exceed threshold.
Summarizes older messages into a compact block, keeps recent turns verbatim.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4

_COMPACT_SYSTEM_PROMPT = (
    "Bạn là công cụ tóm tắt hội thoại. Nhiệm vụ của bạn là tóm gọn "
    "đoạn hội thoại dưới đây thành một bản tóm tắt ngắn gọn bằng tiếng Việt, "
    "giữ lại những thông tin quan trọng sau:\n"
    "1. Chủ đề chính và mục đích của cuộc trò chuyện\n"
    "2. Các quyết định đã được đưa ra\n"
    "3. Các thông tin, số liệu, sự kiện quan trọng\n"
    "4. Các câu hỏi chưa được giải đáp (nếu có)\n"
    "5. Ngữ cảnh cần thiết để tiếp tục cuộc trò chuyện\n\n"
    "Viết tóm tắt dài tối đa 300 từ, chỉ viết phần tóm tắt, không thêm lời bình."
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def count_history_tokens(history: list[dict]) -> int:
    total = 0
    for msg in history:
        total += estimate_tokens(msg.get("content") or "")
    return total


def get_compact_threshold() -> int:
    return int(settings.ai_context_window * settings.ai_compact_threshold_ratio)


def should_compact(history: list[dict]) -> bool:
    total = count_history_tokens(history)
    threshold = get_compact_threshold()
    if total > threshold:
        logger.info(
            "History tokens %d exceeds threshold %d, triggering compaction",
            total,
            threshold,
        )
        return True
    return False


def split_history(history: list[dict]) -> tuple[list[dict], list[dict]]:
    keep_count = min(settings.ai_compact_keep_recent * 2, len(history))
    return history[:-keep_count], history[-keep_count:]


def _build_summarize_messages(history_old: list[dict]) -> list[dict]:
    conversation_text = ""
    for msg in history_old:
        role = "Người dùng" if msg["role"] == "user" else "Trợ lý"
        conversation_text += f"{role}: {msg['content']}\n\n"

    return [
        {"role": "system", "content": _COMPACT_SYSTEM_PROMPT},
        {"role": "user", "content": conversation_text},
    ]


async def compact_history(history: list[dict]) -> list[dict]:
    if not should_compact(history):
        return history

    history_old, history_recent = split_history(history)

    if not history_old or not history_recent:
        return history

    logger.info(
        "Compacting %d old messages (%d tokens) into summary, keeping %d recent turns",
        len(history_old),
        count_history_tokens(history_old),
        len(history_recent),
    )

    summary = await _summarize(history_old)

    if summary:
        summary_msg = {
            "role": "system",
            "content": f"[Tóm tắt hội thoại trước đó]\n{summary}",
        }
        logger.info("Compaction complete: summary=%d chars, %d recent messages kept", len(summary), len(history_recent))
        return [summary_msg] + history_recent

    logger.warning("Compaction returned empty summary, dropping oldest messages instead")
    return history_recent


async def _summarize(history_old: list[dict]) -> str:
    messages = _build_summarize_messages(history_old)

    headers = {"Content-Type": "application/json"}
    api_key = settings.ai_proxy_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{settings.ai_proxy_url.rstrip('/')}/v1/chat/completions"
    body = {
        "model": settings.ai_proxy_default_model or "",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.error("Summarization API error %d: %s", resp.status_code, resp.text[:200])
                return ""

            data = resp.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            return content.strip()
    except Exception as e:
        logger.error("Summarization call failed: %s", e, exc_info=True)
        return ""
