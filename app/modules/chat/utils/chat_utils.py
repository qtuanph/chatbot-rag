"""Utility functions for ChatService."""

from __future__ import annotations
import re
from typing import Any
import nh3
from app.core.config import settings

# Vietnamese + English greeting/social patterns
_GREETING_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(chào|hello|hi|hey|hola|chao|xin chào|chào bạn|chào anh|chào chị)\b", re.IGNORECASE),
    re.compile(r"^(cảm ơn|cám ơn|thank|thanks|thank you|thanks you)\b", re.IGNORECASE),
    re.compile(r"^(tạm biệt|bye|goodbye|tam biet|tạm biệt nhé)\b", re.IGNORECASE),
    re.compile(r"^(bạn (có )?khỏe không|how are you|bạn thế nào)\b", re.IGNORECASE),
    re.compile(r"^(vâng|dạ|ừ|ừm|ok|okay|yeah|yes|vâng ạ|dạ vâng)\b", re.IGNORECASE),
    re.compile(r"^(good morning|good afternoon|good evening|good night)\b", re.IGNORECASE),
    re.compile(r"^(buổi sáng|buổi trưa|buổi chiều|buổi tối)\b", re.IGNORECASE),
    re.compile(r"^(chúc|wish)\b", re.IGNORECASE),
    re.compile(r"^rất vui được gặp (bạn|anh|chị|em)\b", re.IGNORECASE),
    re.compile(r"^(nice to meet|pleased to meet|howdy)\b", re.IGNORECASE),
]


def is_greeting(query: str) -> bool:
    """Detect if query is purely a greeting/social message (no actual question content)."""
    cleaned = query.strip().rstrip(".!?")
    if not cleaned or len(cleaned) > 120:
        return False
    for pattern in _GREETING_PATTERNS:
        if pattern.match(cleaned):
            return True
    return False


def validate_query(query: str) -> None:
    """Validate and sanitize query input. Raises ValueError on failure."""
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    if len(query) > 5000:
        raise ValueError("Query too long (max 5000 characters)")
    sanitized = nh3.clean(query, tags=set(), attributes={})
    if len(sanitized) < len(query) * 0.8:
        raise ValueError("Query contains potentially unsafe content")


def compute_cost(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * settings.ai_input_cost_per_1m + tokens_out * settings.ai_output_cost_per_1m) / 1_000_000


def deduplicate_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group citations by document_id, merge page ranges into compact format."""
    if not citations:
        return []

    doc_groups: dict[str, list[dict]] = {}
    doc_titles: dict[str, str] = {}
    for citation in citations:
        doc_id = citation.get("document_id", "")
        if doc_id not in doc_groups:
            doc_groups[doc_id] = []
            doc_titles[doc_id] = citation.get("title", "Tài liệu")
        doc_groups[doc_id].append(citation)

    result = []
    for doc_id, cites in doc_groups.items():
        pages: set[int] = set()
        for c in cites:
            pr = c.get("page_range")
            if pr:
                try:
                    parts = str(pr).split("-")
                    start = int(parts[0].strip())
                    end = int(parts[-1].strip())
                    pages.update(range(start, end + 1))
                except (ValueError, IndexError):
                    pass

        page_display = ""
        if pages:
            sorted_pages = sorted(pages)
            ranges: list[str] = []
            range_start = sorted_pages[0]
            range_end = sorted_pages[0]
            for p in sorted_pages[1:]:
                if p == range_end + 1:
                    range_end = p
                else:
                    ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
                    range_start = p
                    range_end = p
            ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
            page_display = ", ".join(ranges)

        result.append(
            {
                "document_id": doc_id,
                "title": doc_titles.get(doc_id, "Tài liệu"),
                "pages": page_display,
            }
        )
    return result
