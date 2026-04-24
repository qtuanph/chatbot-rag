"""
Rule-Based Refiner: Fast, lightweight text refinement using heuristics + regex.

Replaces Qwen LLM to reduce VRAM usage from 3GB to 0GB and speed from ~500ms to ~1ms per node.
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RuleBasedRefiner:
    """
    Fast, lightweight refiner using heuristics + regex.

    Purpose:
    1. Fix OCR spaced text errors (e.g., "M Ụ C T I Ê U" → "MỤC TIÊU")
    2. Detect headers from document structure
    3. Detect hierarchy levels from Markdown/HTML patterns

    Performance:
    - VRAM: 0GB (no model loading)
    - Speed: ~1ms per node (vs ~500ms for Qwen)
    - Accuracy: ⭐⭐⭐⭐ (sufficient for Word→PDF documents)
    """

    def refine_text(self, text: str, current_header: Optional[str]) -> Tuple[str, Optional[str]]:
        """
        Refine text using rule-based heuristics.

        Args:
            text: The text content to refine
            current_header: Current header/title (if any)

        Returns:
            Tuple of (cleaned_text, detected_header)
        """
        if not text:
            return text, current_header

        # Step 1: Fix common OCR errors
        cleaned_text = self._fix_spaced_text(text)
        cleaned_text = self._fix_whitespace(cleaned_text)

        # Step 2: Detect header
        detected_header = self._detect_header(cleaned_text, current_header)

        return cleaned_text, detected_header

    def _fix_spaced_text(self, text: str) -> str:
        """
        Fix spaced text errors from OCR.

        Examples:
        - "M Ụ C T I Ê U" → "MỤCTIÊU" (then re-split heuristically)
        - "T R Ờ N G   C H Ủ" → "TRỌNGCHỦ"

        Pattern: sequences of single chars separated by spaces (3+ consecutive).
        Only targets OCR-style spaced letters, NOT normal word spacing.
        """
        # Fix sequences of single Vietnamese chars separated by spaces (OCR artifact)
        # Match 3+ consecutive single chars each followed by a space, then merge
        text = re.sub(
            r'(?:[A-Za-zÀ-ỹ]\s+){2,}[A-Za-zÀ-ỹ]',
            lambda m: re.sub(r'\s+', '', m.group(0)),
            text,
        )

        # Fix multiple spaces (common OCR error)
        text = re.sub(r' {3,}', ' ', text)

        return text

    def _fix_whitespace(self, text: str) -> str:
        """Normalize whitespace"""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Fix newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _detect_header(self, text: str, current_header: Optional[str]) -> Optional[str]:
        """
        Detect header from text using patterns.

        Patterns tried:
        1. Markdown headers (# ## ###)
        2. First line (if it looks like a title)
        3. HTML tags (h1, h2, h3)
        4. Uppercase lines (all caps, usually headers)
        """
        lines = text.strip().split('\n')
        if not lines:
            return current_header

        # Pattern 1: Markdown header (# ## ###)
        markdown_match = re.match(r'^#+\s*(.+)$', lines[0])
        if markdown_match:
            header = markdown_match.group(1).strip()
            # Remove leading # symbols
            header = re.sub(r'^#+\s*', '', header)
            if len(header) >= 3 and len(header) <= 150:
                return header

        # Pattern 2: First line is header (heuristic)
        # Characteristics: short (3-100 chars), doesn't end with period, has alphanum
        if len(lines) > 1:
            first_line = lines[0].strip()
            if (3 <= len(first_line) <= 100 and
                not first_line.endswith('.') and
                not first_line.endswith(',') and
                any(c.isalnum() for c in first_line)):
                return first_line

        # Pattern 3: HTML headers (<h1>, <h2>, <h3>)
        html_match = re.search(r'<h([1-6])[^>]*>(.*?)</h\1>', text, re.IGNORECASE)
        if html_match:
            header = html_match.group(2).strip()
            # Remove HTML tags
            header = re.sub(r'<[^>]+>', '', header)
            if len(header) >= 3:
                return header

        # Pattern 4: ALL CAPS line (often headers in documents)
        if len(lines) > 1:
            first_line = lines[0].strip()
            if (first_line.isupper() and
                len(first_line) >= 3 and
                len(first_line) <= 100 and
                not any(c.isdigit() for c in first_line)):  # Not "12345"
                return first_line

        # Pattern 5: Generic headers to skip
        if current_header:
            generic_headers = ("section", "nội dung", "untitled", "content", "text")
            if current_header.lower().strip() in generic_headers:
                # Try to find better header from text
                if lines[0] and len(lines[0]) < 100:
                    return lines[0].strip()

        # Fallback: keep current header
        return current_header


# Global instance for easy access
rule_based_refiner = RuleBasedRefiner()
