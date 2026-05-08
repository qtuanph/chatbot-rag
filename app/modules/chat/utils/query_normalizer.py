"""
Query Normalizer: Improve cache hit rate by normalizing queries.
Implements lowercase, strip, collapse spaces, and stopword removal.
"""

from __future__ import annotations

import re

DEFAULT_VIETNAMESE_STOPWORDS: set[str] = {
    "xin",
    "chào",
    "bạn",
    "anh",
    "chị",
    "em",
    "ôi",
    "ơi",
    "cảm",
    "ơn",
    "cám",
    "thank",
    "thanks",
    "hello",
    "hi",
    "vui",
    "lòng",
    "xin",
    "please",
    "tôi",
    "muốn",
    "hỏi",
    "cho",
    "biết",
    "làm",
    "sao",
    "để",
    "ạ",
    "ạ?",
    "ơ",
    "ơ?",
    "nha",
    "nhé",
    "vậy",
    "ấy",
    "có",
    "không",
    "được",
    "không?",
    "được không?",
    "là",
    "cái",
    "gì",
    "đi",
    "được",
    "rồi",
    "còn",
}

DEFAULT_ERP_STOPWORDS: set[str] = {
    "phần",
    "mềm",
    "erp",
    "hệ",
    "thống",
    "module",
    "chức",
    "năng",
    "tính",
    "năng",
    "hướng",
    "dẫn",
    "sử",
    "dụng",
    "cách",
    "dùng",
    "xem",
    "thêm",
    "chi",
    "tiết",
    "cụ",
    "thể",
}

ALL_DEFAULT_STOPWORDS = DEFAULT_VIETNAMESE_STOPWORDS | DEFAULT_ERP_STOPWORDS


def normalize_query(
    text: str,
    stopwords: set[str] | None = None,
    remove_stopwords: bool = True,
) -> str:
    """Normalize query text for better cache hit rate."""
    if not text:
        return ""

    normalized = text.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)

    if remove_stopwords and stopwords:
        words = normalized.split()
        filtered = [w for w in words if w not in stopwords]
        normalized = " ".join(filtered)

    return normalized


def remove_stopwords_from_query(text: str, stopwords: set[str] | None = None) -> str:
    """Remove stopwords from query text."""
    return normalize_query(text, stopwords=stopwords or ALL_DEFAULT_STOPWORDS, remove_stopwords=True)


def get_stopwords_for_language(language: str = "vi") -> set[str]:
    """Get stopwords for specific language."""
    if language == "vi":
        return DEFAULT_VIETNAMESE_STOPWORDS
    elif language == "en":
        return DEFAULT_ERP_STOPWORDS
    else:
        return ALL_DEFAULT_STOPWORDS
