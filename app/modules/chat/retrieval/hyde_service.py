"""HyDE — Hypothetical Document Embeddings for short-query retrieval."""

from __future__ import annotations

import logging

from app.adapters.ai.proxy_bridge import AIProxyBridge
from app.core.config import settings

logger = logging.getLogger(__name__)

_HYDE_PROMPT = (
    "Bạn là chuyên gia tạo câu trả lời mẫu cho hệ thống RAG.\n"
    "Dựa trên kiến thức chuyên môn của bạn, hãy viết một đoạn văn ngắn (3-5 câu) "
    "trả lời câu hỏi dưới đây một cách chi tiết, chính xác, bằng tiếng Việt.\n"
    "Đây là câu trả lời GIẢ ĐỊNH — không cần trích dẫn nguồn, "
    "nhưng hãy viết như thể đó là tài liệu tham khảo thực tế.\n\n"
    "Câu hỏi: {query}"
)


async def hyde_generate(query: str) -> str | None:
    """Generate a hypothetical answer document for the given query.

    Uses the auxiliary model (lightweight/fast) to produce a short paragraph
    that mimics a retrieved document. This hypothetical document is then
    embedded and used alongside the original query for retrieval.

    Returns:
        Hypothetical answer text, or None if generation fails.
    """
    prompt = _HYDE_PROMPT.format(query=query)
    provider = AIProxyBridge(model=settings.ai_auxiliary_model or settings.ai_proxy_default_model)
    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
        )
        from app.modules.chat.retrieval.usage_tracker import track_usage

        track_usage(provider, endpoint="hyde")
        answer = (response.get("answer") or "").strip()
        if answer and len(answer) >= 20:
            logger.info("[HyDE] Generated hypothetical answer (%d chars) for: '%s'", len(answer), query[:60])
            return answer
        return None
    except Exception as e:
        logger.warning("[HyDE] Generation failed: %s", e)
        return None
