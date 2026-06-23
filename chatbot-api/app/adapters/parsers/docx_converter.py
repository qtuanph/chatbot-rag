"""
DOCX → PDF converter using LibreOffice headless.
Converts Word documents to PDF before OCR parsing to ensure accurate text extraction.
Flattens Word's internal numbering/styles, producing clean text-only PDF for OCR.
"""

import logging
import os
import subprocess
import tempfile
from typing import Tuple

logger = logging.getLogger(__name__)

# Supported DOCX extensions
SUPPORTED_EXTENSIONS = {".docx", ".doc"}


def is_docx(filename: str) -> bool:
    """Check if file is a DOCX/DOC file that needs conversion."""
    ext = os.path.splitext(filename.lower())[1]
    return ext in SUPPORTED_EXTENSIONS


def convert_docx_to_pdf(content: bytes, filename: str) -> Tuple[bytes, str]:
    """
    Convert DOCX/DOC content to PDF using LibreOffice headless.

    Returns:
        Tuple of (pdf_content, original_filename_with_pdf_ext)

    Raises:
        RuntimeError: If LibreOffice conversion fails
    """
    ext = os.path.splitext(filename.lower())[1]

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type for DOCX→PDF conversion: {ext}")

    base_name = os.path.splitext(os.path.basename(filename))[0]
    pdf_filename = base_name + ".pdf"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write input DOCX to temp file
        input_path = os.path.join(tmpdir, f"input{ext}")
        with open(input_path, "wb") as f:
            f.write(content)

        # Run LibreOffice headless conversion
        # --headless: no GUI
        # --convert-to pdf: output format
        # --outdir: output directory
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            tmpdir,
            input_path,
        ]

        logger.info("Converting %s to PDF via LibreOffice...", filename)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for conversion
                check=False,
            )

            if result.returncode != 0:
                logger.error("LibreOffice conversion failed: %s", result.stderr)
                raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

            # Find the output PDF
            pdf_path = os.path.join(tmpdir, "input.pdf")
            if not os.path.exists(pdf_path):
                # LibreOffice might name it differently, find it
                pdf_files = [f for f in os.listdir(tmpdir) if f.endswith(".pdf")]
                if not pdf_files:
                    raise RuntimeError(f"LibreOffice did not produce PDF output. stderr: {result.stderr}")
                pdf_path = os.path.join(tmpdir, pdf_files[0])

            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

            logger.info("Successfully converted %s to PDF (%d bytes)", filename, len(pdf_content))
            return pdf_content, pdf_filename

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out for %s", filename)
            raise RuntimeError(f"LibreOffice conversion timed out for {filename}")
        except FileNotFoundError:
            logger.error("LibreOffice not found in PATH. Install libreoffice on system.")
            raise RuntimeError(
                "LibreOffice not found. Install with: apt-get install libreoffice"
                if os.path.exists("/etc/debian_version")
                else "LibreOffice not found. Please install LibreOffice on your system."
            )
        except Exception as e:
            logger.exception("Unexpected error during DOCX→PDF conversion")
            raise RuntimeError(f"DOCX→PDF conversion failed: {e}")
