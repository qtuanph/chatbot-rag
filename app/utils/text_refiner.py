"""
Text Refiner: Production-grade OCR cleanup using nh3 and heuristics.
Optimized for technical documents (manuals, guides) to preserve tables/lists.
"""

import re
import nh3
import logging

logger = logging.getLogger(__name__)

# Whitelist tags crucial for technical documentation structure
ALLOWED_TAGS = {
    "p",
    "br",
    "b",
    "i",
    "strong",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "blockquote",
    "code",
    "pre",
}

# No attributes allowed to prevent XSS and style injection
ALLOWED_ATTRIBUTES = {}


class RuleBasedRefiner:
    """Applies high-speed HTML sanitization and regex heuristics to clean OCR text."""

    def __init__(self) -> None:
        # Pre-compile regex for performance
        # 1. Remove zero-width spaces and specific control characters
        self.re_zero_width = re.compile(r"[\u200B-\u200D\uFEFF]")

        # 2. Normalize excessive consecutive blank lines (more than 2 -> exactly 2)
        self.re_blank_lines = re.compile(r"\n{3,}")

        # 3. Fix fragmented words caused by soft hyphens or OCR line breaks
        self.re_hyphen_break = re.compile(r"(\w+)-\n(\w+)")

        # 4. Fix collapsed list items (e.g., "a. item1 b. item2", "1.1 item 1.2 item")
        # Supports: 1.1, 1.1.1, a., b., 1., 2), I., II.
        self.re_list_item_fix = re.compile(r"\s+((?:\d+\.)+\d*|[a-zA-Z0-9][\.\)]|[IVXLCDM]+[\.\)])\s+")

        # 5. Normalize multiple spaces to a single space
        self.re_multiple_spaces = re.compile(r"[^\S\n]{2,}")

    def refine(self, text: str) -> str:
        """
        Clean text using nh3 (Rust) and Regex.
        Safe for concurrent execution via asyncio.to_thread.
        """
        if not text:
            return ""

        try:
            # 1. HTML Sanitization (Rust-powered, < 1ms)
            # Strips malicious tags, scripts, classes, styles but keeps structure
            text = nh3.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

            # 2. Heuristic Cleanup
            text = self.re_zero_width.sub("", text)
            text = self.re_hyphen_break.sub(r"\1\2", text)
            text = self.re_list_item_fix.sub(r"\n\1 ", text)
            text = self.re_multiple_spaces.sub(" ", text)
            text = self.re_blank_lines.sub("\n\n", text)

            return text.strip()
        except Exception as e:
            logger.warning("Text refinement failed, returning original text. Error: %s", e)
            return text

    def refine_nodes(self, nodes: list) -> list:
        """Batch refine node texts."""
        for node in nodes:
            if getattr(node, "text", None):
                node.text = self.refine(node.text)
        return nodes

    def refine_sections(self, sections: list[dict]) -> list[dict]:
        """Batch refine section contents."""
        for sec in sections:
            if "content" in sec and sec["content"]:
                sec["content"] = self.refine(sec["content"])
        return sections


# Singleton instance for easy import

rule_based_refiner = RuleBasedRefiner()
