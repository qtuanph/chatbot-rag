"""Shared helpers for inferring file formats from filenames."""

from __future__ import annotations

import os


def extract_file_format(filename: str) -> str:
    """Extract a normalized file format token from a filename."""
    ext = os.path.splitext(filename.lower())[1].lstrip('.')
    format_map = {
        'pdf': 'pdf',
        'docx': 'docx',
        'doc': 'docx',
        'xlsx': 'xlsx',
        'xls': 'xlsx',
        'txt': 'text',
        'md': 'markdown',
        'html': 'html',
        'htm': 'html',
        'jpg': 'image',
        'png': 'image',
        'gif': 'image',
        'tiff': 'image',
    }
    return format_map.get(ext, ext or 'unknown')