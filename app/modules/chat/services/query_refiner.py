"""Query Refinement - Refine user query for better retrieval quality using AI provider."""

from __future__ import annotations

import logging
from typing import List

from app.adapters.ai.cliproxy_bridge import CLIProxyBridge

logger = logging.getLogger(__name__)

_REFINEMENT_PROMPT = (
    "Bạn là công cụ tối ưu hóa câu truy vấn cho hệ thống RAG. "
    "Nhiệm vụ của bạn là viết lại câu hỏi của người dùng thành một câu truy vấn tối ưu hơn "
    "cho việc tìm kiếm tài liệu.\n\n"
    "## Quy tắc:\n"
    "- Mở rộng các từ viết tắt, thay thế tiếng lóng hoặc từ không chuyên ngành.\n"
    "- Thêm từ khóa liên quan từ ngữ cảnh lịch sử trò chuyện (nếu có).\n"
    "- Giữ nguyên ý định của người dùng.\n"
    "- Trả lời CHỈ câu truy vấn đã được tối ưu hóa, không thêm giải thích.\n"
    "- Ưu tiên ngôn ngữ Tiếng Việt chuyên nghiệp, rõ ràng.\n"
)


async def refine_query(query: str, history: List[dict] | None = None) -> str:
    """Refine a user query for better retrieval.

    Args:
        query: Original user query
        history: Optional conversation history for context

    Returns:
        Refined query string (or original if refinement fails)
    """
    if not query or len(query.strip()) < 5:
        return query

    # Build context from recent history (last 5 messages)
    context_parts = []
    if history:
        recent = history[-5:] if len(history) > 5 else history
        for msg in recent:
            role = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
            content = str(msg.get("content", ""))[:200]
            if content:
                context_parts.append(f"{role}: {content}")

    history_context = "\n".join(context_parts) if context_parts else ""

    prompt = _REFINEMENT_PROMPT
    if history_context:
        prompt += f"\n\nLịch sử trò chuyện gần đây:\n{history_context}\n"
    prompt += f"\nCâu hỏi của người dùng: {query}\n\nCâu truy vấn tối ưu hóa:"

    try:
        provider = CLIProxyBridge()
        response = await provider.chat(messages=[{"role": "user", "content": prompt}])
        refined = response.get("answer", "").strip() if isinstance(response, dict) else ""

        if refined and len(refined) >= 3:
            logger.info("Query refined: '%s' -> '%s'", query[:80], refined[:80])
            return refined
    except Exception as e:
        logger.warning("Query refinement failed, using original: %s", e)

    return query
