"""Image OCR extractor for standalone image uploads.

The extractor acts as a small Facade around three responsibilities:
- validate supported image types
- load and preprocess the image
- delegate OCR to a pluggable engine strategy

The preprocessing behavior is itself a Strategy so we can swap or extend
it without changing the extractor or upload orchestration.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import logging
from PIL import Image

from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.image_preprocessors import (
    BaseImagePreprocessor,
    GrayscaleThresholdPreprocessor,
)
from file_processing.extractors.ocr.ocr_strategy import OCRStrategyFactory
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger(__name__)


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class ImageExtractor:
    """Extract text from image files using a pluggable OCR engine."""

    def __init__(
        self,
        ocr_engine: BaseOCREngine | None = None,
        *,
        preprocessor: BaseImagePreprocessor | None = None,
    ):
        self.ocr_engine = ocr_engine or TesseractEngine(apply_preprocessing=False)
        self.preprocessor = preprocessor or GrayscaleThresholdPreprocessor()

    def _validate_extension(self, file_path: str) -> None:
        extension = os.path.splitext(file_path)[1].lower()
        if extension not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(
                "Unsupported image type. Only PNG, JPG, and JPEG are allowed."
            )

    @staticmethod
    def _split_lines(text: str) -> List[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _load_image(self, file_path: str) -> Image.Image:
        try:
            return Image.open(file_path)
        except OSError as exc:
            raise ValueError("Image file is corrupted or unreadable.") from exc

    def extract(self, file_path: str) -> Dict[str, Any]:
        """Extract OCR text from an image path.

        Returns a payload aligned with the existing extraction contract:
        ``{"content": [{"page": 1, "text": [...] }]}``
        """
        self._validate_extension(file_path)

        try:
            with self._load_image(file_path) as image:
                prepared = self.preprocessor.preprocess(image)
                metadata = self.ocr_engine.extract_text_with_metadata(prepared)
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Image OCR extraction failed.")
            raise ValueError("Image OCR extraction failed.") from exc

        cleanup_result = OCRStrategyFactory.cleanup_text_for_document(
            document_type="image",
            text=metadata.get("text", ""),
            avg_confidence=float(metadata.get("avg_confidence", 0.0)),
            word_details=metadata.get("word_details"),
        )

        lines = self._split_lines(cleanup_result["text"])
        logger.info(
            "Image OCR completed: %d lines extracted (confidence=%.1f%%)",
            len(lines),
            cleanup_result["ocr_metadata"].get("confidence_score", 0.0),
        )

        return {
            "content": [
                {
                    "page": 1,
                    "text": lines,
                    "ocr_metadata": cleanup_result["ocr_metadata"],
                }
            ],
            "ocr_metadata": cleanup_result["ocr_metadata"],
        }
