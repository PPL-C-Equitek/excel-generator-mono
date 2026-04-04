"""Image OCR extractor for standalone image uploads.

This extractor is intentionally small and strategy-driven:
- It accepts any ``BaseOCREngine`` implementation.
- Defaults to ``TesseractEngine`` as the primary OCR engine.
- Performs lightweight preprocessing (grayscale + optional thresholding)
  before sending images to the OCR engine.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from PIL import Image, ImageOps, UnidentifiedImageError

from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.services.ocr_config import (
    IMAGE_OCR_APPLY_THRESHOLD,
    IMAGE_OCR_THRESHOLD,
)

logger = logging.getLogger(__name__)


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class ImageExtractor:
    """Extract text from image files using a pluggable OCR engine."""

    def __init__(
        self,
        ocr_engine: BaseOCREngine | None = None,
        *,
        apply_thresholding: bool = IMAGE_OCR_APPLY_THRESHOLD,
        threshold_value: int = IMAGE_OCR_THRESHOLD,
    ):
        self.ocr_engine = ocr_engine or TesseractEngine(apply_preprocessing=True)
        self.apply_thresholding = apply_thresholding
        self.threshold_value = threshold_value

    def _validate_extension(self, file_path: str) -> None:
        extension = os.path.splitext(file_path)[1].lower()
        if extension not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(
                "Unsupported image type. Only PNG, JPG, and JPEG are allowed."
            )

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)

        if not self.apply_thresholding:
            return grayscale

        threshold = self.threshold_value
        return grayscale.point(lambda pixel: 255 if pixel > threshold else 0, mode="1")

    @staticmethod
    def _split_lines(text: str) -> List[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def extract(self, file_path: str) -> Dict[str, Any]:
        """Extract OCR text from an image path.

        Returns a payload aligned with the existing extraction contract:
        ``{"content": [{"page": 1, "text": [...] }]}``
        """
        self._validate_extension(file_path)

        try:
            with Image.open(file_path) as image:
                prepared = self._preprocess_for_ocr(image)
                text, confidence = self.ocr_engine.extract_text_with_confidence(prepared)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Image file is corrupted or unreadable.") from exc
        except Exception as exc:
            logger.exception("Image OCR extraction failed.")
            raise ValueError("Image OCR extraction failed.") from exc

        lines = self._split_lines(text)
        logger.info(
            "Image OCR completed: %d lines extracted (confidence=%.1f%%)",
            len(lines),
            confidence,
        )

        return {
            "content": [
                {
                    "page": 1,
                    "text": lines,
                }
            ]
        }
