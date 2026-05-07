"""
Multi-Query Expansion — generates query variants for broader retrieval coverage.

Takes the user's original query and generates N reformulations using the AI provider.
Each variant uses different vocabulary while preserving the original intent.

This improves recall for queries where the user's wording doesn't match document phrasing.
"""

from __future__ import annotations

import logging

from app.adapters.ai import build_ai_provider
from app.core.config import settings

logger = logging.getLogger(__name__)


async def expand_query(query: str, n_variants: int | None = None) -> list[str]:
    """Generate query variants for broader retrieval coverage.

    Args:
        query: Original user query
        n_variants: Number of variants to generate (default: from settings)

    Returns:
        List containing original query + variants

    Raises:
        Exception: If AI provider fails to generate variants
    """
    n = n_variants or settings.retrieval_query_expansion_variants

    prompt = (
        f"Viết lại câu hỏi sau thành {n} cách khác nhau, "
        f"giữ nguyên ý nghĩa nhưng dùng từ vựng khác. "
        f"Mỗi câu viết trên 1 dòng, không đánh số, không giải thích.\n\n"
        f"Câu hỏi: {query}"
    )

    provider = build_ai_provider()
    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            context=[],
            citations=[],
        )
    except Exception as e:
        logger.warning("Query expansion AI call failed: %s", e)
        return [query]

    answer_text = response.get("answer", "") if isinstance(response, dict) else ""
    if not answer_text:
        return [query]

    variants = [line.strip().lstrip("0123456789.-) ") for line in answer_text.split("\n") if line.strip()]

    # Deduplicate while preserving order
    seen = {query.lower()}
    unique = [query]
    for v in variants[:n]:
        if v.lower() not in seen:
            seen.add(v.lower())
            unique.append(v)

    logger.info("Query expansion: %d variants for '%s'", len(unique) - 1, query[:50])
    return unique
