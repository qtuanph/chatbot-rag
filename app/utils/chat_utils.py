"""Utility functions for ChatService."""

from __future__ import annotations
from typing import Any
import nh3
from app.core.config import settings


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


def build_user_friendly_error(error: Exception) -> str:
    """Convert technical errors to user-friendly Vietnamese messages."""
    error_str = str(error).lower()
    if "timeout" in error_str or "timed out" in error_str:
        return "AI Model phản hồi quá chậm. Vui lòng thử câu hỏi ngắn hơn hoặc thử lại sau."
    elif "rate limit" in error_str or "429" in error_str:
        return "Đã đạt giới hạn request. Vui lòng chờ một chút rồi thử lại."
    elif "safety" in error_str or "blocked" in error_str:
        return "Nội dung không được phép. Vui lòng thử câu hỏi khác."
    elif "connection" in error_str:
        return "Lỗi kết nối với AI Model. Vui lòng kiểm tra mạng và thử lại."
    else:
        return "Lỗi không xác định. Vui lòng thử lại sau."
