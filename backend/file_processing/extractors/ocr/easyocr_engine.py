"""
EasyOCR-based OCR engine — fallback for handwritten text and low-confidence scans.

EasyOCR uses deep-learning models and generally handles handwritten text,
mixed layouts, and non-Latin scripts better than Tesseract.  It is used as
a secondary engine when the primary Tesseract engine reports low confidence.

The Reader instance is cached at the module level to avoid reloading the
(large) recognition models on every call.
"""

import logging
from typing import Any, List, Tuple

import numpy as np
from PIL import Image

import easyocr

from .base_ocr_engine import BaseOCREngine
from file_processing.services.ocr_config import (
    EASYOCR_GPU,
    EASYOCR_LANGUAGES,
)

logger = logging.getLogger(__name__)

_reader_cache = None


def _get_reader(languages: List[str], gpu: bool):
    """Return a cached ``easyocr.Reader`` instance."""
    global _reader_cache # noqa: PLW0603
    if _reader_cache is None:
        logger.info("Initializing EasyOCR Reader (languages=%s, gpu=%s)", languages, gpu)
        _reader_cache = easyocr.Reader(languages, gpu=gpu)
    return _reader_cache


class EasyOCREngine(BaseOCREngine):
    """EasyOCR engine, particularly useful for handwritten text."""

    def __init__(self, *, languages: List[str] | None = None, gpu: bool | None = None):
        """
        Args:
            languages: List of language codes (e.g. ``["en"]``).
                       Falls back to ``EASYOCR_LANGUAGES`` from config.
            gpu: Whether to use GPU.  Falls back to ``EASYOCR_GPU``.
        """
        self.languages = languages or EASYOCR_LANGUAGES
        self.gpu = gpu if gpu is not None else EASYOCR_GPU

    def _image_to_array(self, image: Any) -> np.ndarray:
        """Convert various image types to a numpy array for EasyOCR."""
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, Image.Image):
            return np.array(image)
        return image

    def extract_text(self, image: Any) -> str:
        """Extract text using EasyOCR and return concatenated string."""
        reader = _get_reader(self.languages, self.gpu)
        img_array = self._image_to_array(image)

        results = reader.readtext(img_array)
        lines = [text for (_, text, _) in results]
        return "\n".join(lines)

    def extract_text_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Return ``(text, avg_confidence_percent)`` from EasyOCR.

        EasyOCR reports confidence as a float in [0, 1]; we scale to [0, 100]
        for consistency with the Tesseract engine.
        """
        reader = _get_reader(self.languages, self.gpu)
        img_array = self._image_to_array(image)

        results = reader.readtext(img_array)

        lines = []
        confidences = []
        for _, text, conf in results:
            lines.append(text)
            confidences.append(conf * 100)

        text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        logger.debug(
            "EasyOCR: %d text regions, avg confidence %.1f%%",
            len(lines), avg_conf,
        )
        return text, avg_conf
