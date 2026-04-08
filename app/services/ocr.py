from __future__ import annotations

from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps
from paddleocr import PaddleOCR

from app.core.config import settings


class OCRService:
    def __init__(self) -> None:
        self.provider = settings.ocr_provider.lower().strip()
        if self.provider != "paddle":
            raise ValueError("OCR provider must be paddle")
        self._paddle = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)

    def image_to_text(self, content: bytes) -> str:
        image = Image.open(BytesIO(content)).convert("RGB")
        image = ImageOps.autocontrast(image)

        result = self._paddle.ocr(np.array(image), cls=True)
        lines: list[str] = []
        for block in result[0] or []:
            text = block[1][0]
            if text:
                lines.append(text)
        return "\n".join(lines).strip()


@lru_cache
def get_ocr_service() -> OCRService:
    return OCRService()
