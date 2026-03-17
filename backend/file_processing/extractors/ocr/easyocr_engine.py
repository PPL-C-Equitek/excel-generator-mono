"""
EasyOCR-based OCR engine — primary engine for scanned and handwritten text.

EasyOCR uses deep-learning CRNN models and handles:
- Scanned printed text
- Handwritten text
- Mixed layouts and non-Latin scripts

much better than traditional OCR engines like Tesseract.

The Reader instance is cached at the module level to avoid reloading the
(large) recognition models on every call.

Light preprocessing (upscale → grayscale → CLAHE → denoise) is applied
by default.  Heavy binarisation is intentionally avoided because EasyOCR's
neural network works better on grayscale images with natural contrast.

Line reconstruction:
  EasyOCR returns individual text regions with bounding boxes.  For
  financial documents (invoices, receipts, statements) it is critical
  to reconstruct visual lines so that amounts like "Rp 1.000.000" or
  table rows like "Item  Qty  Price" stay intact.  We cluster text
  regions by vertical midpoint and join each cluster left-to-right.
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
    EASYOCR_LINE_Y_THRESHOLD,
)

logger = logging.getLogger(__name__)

_reader_cache = None


def _get_reader(languages: List[str], gpu: bool):
    """Return a cached ``easyocr.Reader`` instance."""
    global _reader_cache  # noqa: PLW0603
    if _reader_cache is None:
        logger.info("Initializing EasyOCR Reader (languages=%s, gpu=%s)", languages, gpu)
        _reader_cache = easyocr.Reader(languages, gpu=gpu)
    return _reader_cache


def _group_into_lines(
    results: list,
    y_threshold: float = EASYOCR_LINE_Y_THRESHOLD,
) -> List[Tuple[str, List[float]]]:
    """Group EasyOCR text regions into visual lines using bounding-box geometry.

    EasyOCR returns ``(bbox, text, confidence)`` per detected region.
    Financial documents need these regions merged into visual lines so
    that amounts, table rows, and labels stay together.

    Algorithm:
        1. Compute vertical midpoint for each region.
        2. Sort all regions top-to-bottom by midpoint.
        3. Walk through sorted regions; start a new line whenever the
           midpoint gap exceeds *y_threshold* × average text height.
        4. Within each line, sort regions left-to-right by X.
        5. Join text fragments with a space.

    Args:
        results: Raw EasyOCR output — list of ``(bbox, text, conf)``.
        y_threshold: Fraction of average text height used as the
                     line-break threshold.

    Returns:
        List of ``(line_text, [conf1, conf2, ...])`` tuples, one per
        visual line, ordered top-to-bottom.
    """
    if not results:
        return []

    items = []
    for bbox, text, conf in results:
        ys = [pt[1] for pt in bbox]
        xs = [pt[0] for pt in bbox]
        y_mid = (min(ys) + max(ys)) / 2.0
        height = max(ys) - min(ys)
        x_left = min(xs)
        items.append({
            "text": text,
            "conf": conf,
            "y_mid": y_mid,
            "height": height,
            "x_left": x_left,
        })

    avg_height = sum(it["height"] for it in items) / len(items) if items else 20
    gap_threshold = max(avg_height * y_threshold, 5)

    items.sort(key=lambda it: it["y_mid"])
    lines: List[List[dict]] = [[items[0]]]
    for item in items[1:]:
        if abs(item["y_mid"] - lines[-1][-1]["y_mid"]) <= gap_threshold:
            lines[-1].append(item)
        else:
            lines.append([item])

    merged: List[Tuple[str, List[float]]] = []
    for line_items in lines:
        line_items.sort(key=lambda it: it["x_left"])
        line_text = " ".join(it["text"] for it in line_items)
        line_confs = [it["conf"] for it in line_items]
        merged.append((line_text, line_confs))

    return merged


class EasyOCREngine(BaseOCREngine):
    """EasyOCR engine — primary engine for scanned & handwritten documents."""

    def __init__(
        self,
        *,
        languages: List[str] | None = None,
        gpu: bool | None = None,
        apply_preprocessing: bool = True,
    ):
        """
        Args:
            languages: List of language codes (e.g. ``["en"]``).
                       Falls back to ``EASYOCR_LANGUAGES`` from config.
            gpu: Whether to use GPU.  Falls back to ``EASYOCR_GPU``.
            apply_preprocessing: If True, apply light preprocessing
                                 (upscale, grayscale, CLAHE, denoise)
                                 before OCR.  No binarisation is applied.
        """
        self.languages = languages or EASYOCR_LANGUAGES
        self.gpu = gpu if gpu is not None else EASYOCR_GPU
        self.apply_preprocessing = apply_preprocessing

    def _preprocess(self, image: Any) -> np.ndarray:
        """Apply light preprocessing suitable for EasyOCR.

        Pipeline: upscale → grayscale → CLAHE → median denoise.

        Heavy binarisation (thresholding) is intentionally skipped because
        EasyOCR's deep-learning models work best on natural grayscale images.
        """
        from file_processing.services.image_preprocessing import (
            upscale_image,
            convert_to_grayscale,
            normalize_contrast,
            remove_noise,
        )

        img_array = self._image_to_array(image)
        try:
            img_array = upscale_image(img_array)
            img_array = convert_to_grayscale(img_array)
            img_array = normalize_contrast(img_array)
            img_array = remove_noise(img_array)
        except Exception:
            logger.warning(
                "EasyOCR preprocessing failed; using original image.",
                exc_info=True,
            )
            return self._image_to_array(image)
        return img_array

    def _image_to_array(self, image: Any) -> np.ndarray:
        """Convert various image types to a numpy array for EasyOCR."""
        if isinstance(image, np.ndarray):
            return image
        if isinstance(image, Image.Image):
            return np.array(image)
        return image

    def _prepare(self, image: Any) -> np.ndarray:
        """Prepare an image for OCR: optionally preprocess, then convert."""
        if self.apply_preprocessing:
            return self._preprocess(image)
        return self._image_to_array(image)

    def extract_text(self, image: Any) -> str:
        """Extract text using EasyOCR and return line-by-line string.

        Text regions are spatially grouped into visual lines using
        bounding-box Y-coordinates, then joined left-to-right within
        each line.  This preserves financial data like ``Rp 1.000.000``
        and table-row structure.
        """
        reader = _get_reader(self.languages, self.gpu)
        img_array = self._prepare(image)

        results = reader.readtext(img_array)
        lines = _group_into_lines(results)
        return "\n".join(text for text, _ in lines)

    def extract_text_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Return ``(text, avg_confidence_percent)`` from EasyOCR.

        Text is reconstructed line-by-line using spatial grouping.
        Confidence is the average across all detected text regions,
        scaled to [0, 100].
        """
        reader = _get_reader(self.languages, self.gpu)
        img_array = self._prepare(image)

        results = reader.readtext(img_array)
        lines = _group_into_lines(results)

        all_text_lines = []
        all_confs = []
        for line_text, confs in lines:
            all_text_lines.append(line_text)
            all_confs.extend(confs)

        text = "\n".join(all_text_lines)
        avg_conf = (
            sum(c * 100 for c in all_confs) / len(all_confs)
            if all_confs else 0.0
        )

        logger.info(
            "EasyOCR: %d text regions → %d lines, avg confidence %.1f%%",
            sum(len(c) for _, c in lines), len(lines), avg_conf,
        )
        return text, avg_conf
