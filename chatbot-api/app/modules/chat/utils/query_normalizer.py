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
    "please",
    "tôi",
    "muốn",
    "hỏi",
    "cho",
    "biết",
    "làm",
    "để",
    "ạ",
    "ơ",
    "nha",
    "nhé",
    "vậy",
    "ấy",
    "đi",
    "rồi",
    "dạ",
    "vâng",
    "thưa",
    "thì",
    "mà",
    "là",
    "rằng",
    "nhưng",
    "tuy",
    "này",
    "kia",
    "đó",
    "đấy",
    "nọ",
    "nhỉ",
    "hả",
    "thế",
    "nào",
    "đâu",
    "nữa",
    "luôn",
    "cái",
}

DEFAULT_ERP_PHRASES: list[str] = [
    "phần mềm erp",
    "phần mềm",
    "hệ thống",
    "chi tiết",
    "cụ thể",
]

ALL_DEFAULT_STOPWORDS = DEFAULT_VIETNAMESE_STOPWORDS


def normalize_query(
    text: str,
    stopwords: set[str] | None = None,
    remove_stopwords: bool = True,
) -> str:
    """Normalize query text for better cache hit rate."""
    if not text:
        return ""

    normalized = text.lower()

    # Remove specific ERP phrases safely
    for phrase in DEFAULT_ERP_PHRASES:
        normalized = normalized.replace(phrase, "")

    # Strip punctuation
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = normalized.strip()
    normalized = re.sub(r"\s+", " ", normalized)

    if remove_stopwords and stopwords:
        words = normalized.split()
        filtered = [w for w in words if w not in stopwords]
        normalized = " ".join(filtered)

    return normalized


def remove_stopwords_from_query(text: str, stopwords: set[str] | None = None) -> str:
    """Remove stopwords from query text."""
    return normalize_query(
        text, stopwords=stopwords or ALL_DEFAULT_STOPWORDS, remove_stopwords=True
    )


def get_stopwords_for_language(language: str = "vi") -> set[str]:
    """Get stopwords for specific language."""
    if language == "vi":
        return DEFAULT_VIETNAMESE_STOPWORDS
    if language == "en":
        return set()
    return ALL_DEFAULT_STOPWORDS
