"""
Tesseract OCR engine with configurable parameters and image preprocessing.
"""

import logging
from typing import Any, Tuple
import pytesseract

from .base_ocr_engine import BaseOCREngine
from file_processing.services.ocr_config import (
    TESSERACT_LANG,
    get_tesseract_config,
)
from file_processing.services.image_preprocessing import preprocess_image

logger = logging.getLogger(__name__)

class TesseractEngine(BaseOCREngine):
    """Tesseract-based OCR with configurable engine/segmentation modes."""

    def __init__(self, *, lang: str | None = None, custom_config: str | None = None,
                 apply_preprocessing: bool = True):
        """
        Args:
            lang: Tesseract language string (e.g. ``"eng"``).
                  Falls back to ``TESSERACT_LANG`` from config.
            custom_config: Full Tesseract CLI config override.
                           Falls back to ``get_tesseract_config()``.
            apply_preprocessing: If True, run the OpenCV preprocessing
                                 pipeline on each image before OCR.
        """
        self.lang = lang or TESSERACT_LANG
        self.config = custom_config or get_tesseract_config()
        self.apply_preprocessing = apply_preprocessing

    def _prepare_image(self, image: Any) -> Any:
        """Optionally preprocess *image* before feeding it to Tesseract."""
        if not self.apply_preprocessing:
            return image
        try:
            return preprocess_image(image)
        except Exception:
            # If preprocessing fails, use the original image and log a warning rather than crashing.
            logger.warning(
                "Image preprocessing failed; proceeding with original image.",
                exc_info=True,
            )
            return image

    def extract_text(self, image: Any) -> str:  # noqa: D401
        """Return OCR text extracted from *image*."""
        if pytesseract is None:
            raise ImportError("pytesseract is not installed or available.")

        prepared = self._prepare_image(image)
        return pytesseract.image_to_string(
            prepared, lang=self.lang, config=self.config,
        )

    def extract_text_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Return ``(text, avg_confidence)`` using Tesseract word data.

        *avg_confidence* is the mean of per-word confidences reported by
        ``image_to_data()``.  Words with confidence ``-1`` (rejected) are
        excluded from the average.
        """
        if pytesseract is None:
            raise ImportError("pytesseract is not installed or available.")

        prepared = self._prepare_image(image)

        # image_to_data returns a TSV; output_type=dict gives us lists.
        data = pytesseract.image_to_data(
            prepared, lang=self.lang, config=self.config,
            output_type=pytesseract.Output.DICT,
        )

        # Build full text from the "text" column.
        words = [t for t in data.get("text", []) if t.strip()]
        text = " ".join(words)

        # Calculate average confidence (only for real words, conf != -1).
        confidences = [
            c for c in data.get("conf", [])
            if isinstance(c, (int, float)) and c >= 0
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        logger.debug(
            "Tesseract OCR: %d words, avg confidence %.1f%%",
            len(words), avg_conf,
        )
        return text, avg_conf
