from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from app.core.config import settings


class OCRService:
    def __init__(self) -> None:
        self.provider = settings.ocr_provider.lower().strip()
        if self.provider != "paddle":
            raise ValueError("OCR provider must be paddle")
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError(
                "PaddleOCR is not available. Ensure paddleocr and paddlepaddle are installed correctly."
            ) from exc

        self._paddle = self._build_paddle(PaddleOCR)

    @staticmethod
    def _build_paddle(PaddleOCR):
        # PaddleOCR 3.x has API changes versus 2.x, so we try modern/light args first.
        for kwargs in (
            {"lang": settings.ocr_language, "use_gpu": False},
            {
                "lang": settings.ocr_language,
                "use_angle_cls": settings.ocr_use_angle_cls,
                "show_log": False,
                "use_gpu": False,
            },
            {},
        ):
            try:
                return PaddleOCR(**kwargs)
            except TypeError:
                continue

        raise RuntimeError("Unable to initialize PaddleOCR with supported constructor arguments")

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
