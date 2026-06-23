"""MarkdownCleaner — preprocess OCR markdown before heading-aware chunking."""

from __future__ import annotations

import re

# Header/footer patterns known from scanned PDFs
HEADER_FOOTER_PATTERNS: list[re.Pattern] = [
    re.compile(r"SSE\.,?\s*JSC\.?\s*\d*/*\d*", re.IGNORECASE),
    re.compile(r"^\d+\s*/+\s*\d+\s*$"),
]

# Dot-leader patterns used in Table of Contents
TOC_DOT_LEADER: re.Pattern = re.compile(r"[\.•…]{4,}")


class MarkdownCleaner:
    """Preprocess markdown text to remove OCR artifacts before chunking.

    Applied upstream of MarkdownNodeParser to reduce noisy section boundaries.
    """

    def __init__(self) -> None:
        pass

    def clean(self, markdown_text: str) -> str:
        lines = markdown_text.split("\n")
        cleaned: list[str] = []
        prev_blank = False

        for line in lines:
            stripped = line.strip()

            # 1. Remove standalone page numbers (pure digit lines)
            if self._is_page_number(stripped):
                continue

            # 2. Remove header/footer noise
            if self._is_header_footer(stripped):
                continue

            # 3. Remove TOC dot-leader lines
            if self._is_toc_line(stripped):
                continue

            # 4. Collapse multiple blank lines into one
            is_blank = not stripped
            if is_blank and prev_blank:
                continue
            prev_blank = is_blank

            cleaned.append(line)

        return "\n".join(cleaned)

    @staticmethod
    def _is_page_number(text: str) -> bool:
        if not text:
            return False
        # Pure digits, 1-4 chars (common page number range)
        return bool(re.match(r"^\d{1,4}$", text))

    @staticmethod
    def _is_header_footer(text: str) -> bool:
        return any(p.search(text) for p in HEADER_FOOTER_PATTERNS)

    @staticmethod
    def _is_toc_line(text: str) -> bool:
        if "..." not in text:
            return False
        # Remove markdown heading prefix for check
        body = text.lstrip("# ")
        return bool(TOC_DOT_LEADER.search(body))
