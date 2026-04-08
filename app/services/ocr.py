from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import importlib
import re
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import fitz
from PIL import Image, ImageOps

from app.core.config import settings


class OCRService:
    def __init__(self) -> None:
        self.provider = settings.ocr_provider.lower().strip()
        if self.provider != "paddle":
            raise ValueError("OCR provider must be paddle")
        try:
            import paddle
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError(
                "PaddleOCR is not available. Ensure paddleocr and paddlepaddle are installed correctly."
            ) from exc

        self._use_gpu = self._resolve_use_gpu(paddle)
        self._paddle = self._build_paddle(PaddleOCR, use_gpu=self._use_gpu)

    @staticmethod
    def _resolve_use_gpu(paddle) -> bool:
        mode = str(settings.ocr_use_gpu).strip().lower() or "auto"
        has_cuda_build = bool(getattr(paddle.device, "is_compiled_with_cuda", lambda: False)())
        has_cuda_device = False
        try:
            has_cuda_device = bool(getattr(paddle.device, "cuda", None) and paddle.device.cuda.device_count() > 0)
        except Exception:
            has_cuda_device = False

        gpu_available = has_cuda_build and has_cuda_device
        if mode in {"auto", "gpu"}:
            return gpu_available
        if mode in {"true", "1", "yes"}:
            return gpu_available
        return False

    @staticmethod
    def _build_paddle(PaddleOCR, *, use_gpu: bool):
        # PaddleOCR 3.x has API changes versus 2.x, so we try modern/light args first.
        attempts = []
        if use_gpu:
            attempts.extend(
                [
                    {"lang": settings.ocr_language, "use_gpu": True, "show_log": False},
                    {
                        "lang": settings.ocr_language,
                        "use_angle_cls": settings.ocr_use_angle_cls,
                        "show_log": False,
                        "use_gpu": True,
                    },
                ]
            )
        attempts.extend(
            [
                {"lang": settings.ocr_language, "use_gpu": False, "show_log": False},
                {
                    "lang": settings.ocr_language,
                    "use_angle_cls": settings.ocr_use_angle_cls,
                    "show_log": False,
                    "use_gpu": False,
                },
                {},
            ]
        )

        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                return PaddleOCR(**kwargs)
            except Exception as exc:
                last_error = exc
                continue

        raise RuntimeError("Unable to initialize PaddleOCR with supported constructor arguments") from last_error

    def image_to_text(self, content: bytes) -> str:
        image = Image.open(BytesIO(content)).convert("RGB")
        image = ImageOps.autocontrast(image)
        image_array = np.array(image)

        result: Any = None

        if hasattr(self._paddle, "ocr"):
            try:
                result = self._paddle.ocr(image_array, cls=settings.ocr_use_angle_cls)
            except Exception:
                result = None

        if result is None and hasattr(self._paddle, "predict"):
            try:
                result = self._paddle.predict(input=image_array)
            except Exception:
                with NamedTemporaryFile(suffix=".png") as tmp:
                    image.save(tmp.name, format="PNG")
                    result = self._paddle.predict(input=tmp.name)

        lines = self._extract_text_lines(result)
        return self._normalize_output(lines)

    def document_to_markdown(self, content: bytes, *, filetype: str) -> str:
        filetype = filetype.lower().strip()
        if filetype != "pdf":
            text = self.image_to_text(content)
            return f"# Document\n\n{text}" if text else ""

        if settings.ocr_markdown_engine in {"marker", "auto"}:
            markdown = self._marker_pdf_to_markdown(content)
            if markdown:
                return markdown

        return self._builtin_pdf_to_markdown(content)

    def _marker_pdf_to_markdown(self, content: bytes) -> str:
        try:
            mod = importlib.import_module("marker.convert")
        except Exception:
            return ""

        with NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(content)
            tmp.flush()
            for fn_name in ("convert_single_pdf", "convert_pdf"):
                fn = getattr(mod, fn_name, None)
                if fn is None:
                    continue
                try:
                    result = fn(tmp.name)
                except Exception:
                    continue

                if isinstance(result, str) and result.strip():
                    return result.strip()
                if isinstance(result, dict):
                    for key in ("markdown", "content", "text"):
                        value = result.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        return ""

    def _builtin_pdf_to_markdown(self, content: bytes) -> str:
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            chunks: list[str] = []
            for idx, page in enumerate(doc, start=1):
                if settings.ocr_layout_analysis:
                    raw_text = self._extract_layout_text(page)
                else:
                    raw_text = page.get_text("text")

                text = self._normalize_output([line for line in raw_text.splitlines() if line.strip()])
                if not text:
                    text = self.image_to_text(page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png"))
                if not text:
                    continue

                chunks.append(f"# Page {idx}")
                for line in text.splitlines():
                    candidate = " ".join(line.split())
                    if not candidate:
                        continue
                    if self._looks_like_heading_candidate(candidate):
                        chunks.append(f"## {candidate}")
                    else:
                        chunks.append(candidate)
                chunks.append("")

            return "\n".join(chunks).strip()
        finally:
            doc.close()

    @staticmethod
    def _extract_layout_text(page) -> str:
        try:
            data = page.get_text("dict")
        except Exception:
            return page.get_text("text")

        lines: list[str] = []
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(str(span.get("text", "")) for span in spans).strip()
                if text:
                    lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def _looks_like_heading_candidate(line: str) -> bool:
        if len(line) < 3 or len(line) > 100:
            return False
        if re.match(r"^(\d+(?:\.\d+){0,4})\s+\S+", line):
            return True
        if re.match(r"^(CHAPTER|CHƯƠNG|MỤC|PHẦN|SECTION|ARTICLE)\b", line, flags=re.IGNORECASE):
            return True
        words = line.split()
        if len(words) <= 10 and line.isupper():
            return True
        return False

    def _extract_text_lines(self, result: Any) -> list[str]:
        if result is None:
            return []

        # PaddleOCR 2.x classic output format.
        if isinstance(result, list) and result and isinstance(result[0], list):
            lines: list[str] = []
            for block in result[0] or []:
                if (
                    isinstance(block, (list, tuple))
                    and len(block) > 1
                    and isinstance(block[1], (list, tuple))
                    and block[1]
                    and isinstance(block[1][0], str)
                ):
                    text = block[1][0].strip()
                    if text:
                        lines.append(text)
            if lines:
                return lines

        collected: list[str] = []
        self._collect_strings(result, collected)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in collected:
            text = item.strip()
            if not text or not self._is_text_like(text):
                continue
            if text not in seen:
                seen.add(text)
                deduped.append(text)
        return deduped

    def _collect_strings(self, value: Any, bucket: list[str]) -> None:
        if value is None:
            return
        if isinstance(value, str):
            bucket.append(value)
            return
        if isinstance(value, dict):
            matched = False
            for key in ("text", "texts", "rec_text", "rec_texts", "transcription"):
                if key in value:
                    matched = True
                    self._collect_strings(value[key], bucket)
            if not matched:
                for item in value.values():
                    self._collect_strings(item, bucket)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._collect_strings(item, bucket)
            return
        if hasattr(value, "__dict__"):
            self._collect_strings(vars(value), bucket)
            return

    @staticmethod
    def _is_text_like(text: str) -> bool:
        stripped = text.strip()
        if len(stripped) < 2:
            return False
        alnum_count = sum(ch.isalnum() for ch in stripped)
        return alnum_count >= max(2, len(stripped) // 4)

    @staticmethod
    def _normalize_output(lines: list[str]) -> str:
        normalized: list[str] = []
        for line in lines:
            clean = " ".join(line.split())
            if clean:
                normalized.append(clean)
        return "\n".join(normalized).strip()


@lru_cache
def get_ocr_service() -> OCRService:
    return OCRService()
