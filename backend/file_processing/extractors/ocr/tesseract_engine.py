"""
Tesseract OCR engine with multi-PSM strategy and image preprocessing.

The engine tries multiple PSM (Page Segmentation Mode) values and picks
the result with the highest average confidence, which significantly
improves accuracy on documents with varying layouts.
"""

import logging
from typing import Any, List, Tuple
import pytesseract

from .base_ocr_engine import BaseOCREngine
from file_processing.services.ocr_config import (
    TESSERACT_CONFIDENCE_EARLY_EXIT,
    TESSERACT_PSM_MODES,
    get_tesseract_lang,
    get_tesseract_config,
)
from file_processing.services.image_preprocessing import preprocess_image

logger = logging.getLogger(__name__)


class TesseractEngine(BaseOCREngine):
    """Tesseract-based OCR with multi-PSM strategy and preprocessing."""

    def __init__(self, *, lang: str | None = None, custom_config: str | None = None,
                 apply_preprocessing: bool = True,
                 psm_modes: List[int] | None = None):
        """
        Args:
            lang: Tesseract language string (e.g. ``"eng"``).
                  Falls back to ``TESSERACT_LANG`` from config.
            custom_config: Full Tesseract CLI config override.
                           When set, multi-PSM is disabled and this config
                           is used as-is.
            apply_preprocessing: If True, run the OpenCV preprocessing
                                 pipeline on each image before OCR.
            psm_modes: List of PSM modes to try (best confidence wins).
                       Falls back to ``TESSERACT_PSM_MODES`` from config.
                       Ignored when *custom_config* is provided.
        """
        self.lang = lang or get_tesseract_lang()
        self._custom_config = custom_config
        self.apply_preprocessing = apply_preprocessing
        self.psm_modes = psm_modes or TESSERACT_PSM_MODES

    def _prepare_image(self, image: Any) -> Any:
        """Optionally preprocess *image* before feeding it to Tesseract."""
        if not self.apply_preprocessing:
            return image
        try:
            return preprocess_image(image)
        except Exception:
            logger.warning(
                "Image preprocessing failed; proceeding with original image.",
                exc_info=True,
            )
            return image

    def _run_tesseract_data(self, prepared, config: str) -> Tuple[str, float]:
        """Run ``image_to_data`` and return ``(text, avg_conf)``.

        Words are grouped by (block_num, par_num, line_num) so the
        returned text preserves line-by-line structure — critical for
        financial documents where table rows must stay intact.
        """
        data = pytesseract.image_to_data(
            prepared, lang=self.lang, config=config,
            output_type=pytesseract.Output.DICT,
        )

        line_map: dict[tuple[int, int, int], list[str]] = {}
        all_confidences: list[float] = []

        for i, word in enumerate(data.get("text", [])):
            if not word.strip():
                continue
            key = (
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i],
            )
            line_map.setdefault(key, []).append(word)

            conf = data["conf"][i]
            if isinstance(conf, (int, float)) and conf >= 0:
                all_confidences.append(float(conf))

        lines = [
            " ".join(words)
            for _, words in sorted(line_map.items())
        ]
        text = "\n".join(lines)

        avg_conf = (
            sum(all_confidences) / len(all_confidences)
            if all_confidences else 0.0
        )
        return text, avg_conf

    def extract_text(self, image: Any) -> str:  # noqa: D401
        """Return OCR text extracted from *image*."""
        if pytesseract is None:
            raise ImportError("pytesseract is not installed or available.")

        prepared = self._prepare_image(image)

        if self._custom_config:
            return pytesseract.image_to_string(
                prepared, lang=self.lang, config=self._custom_config,
            )

        best_text = ""
        for psm in self.psm_modes:
            config = get_tesseract_config(psm=psm)
            text = pytesseract.image_to_string(
                prepared, lang=self.lang, config=config,
            )
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
        return best_text

    def extract_text_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Return ``(text, avg_confidence)`` using a multi-PSM strategy.

        Each PSM mode in ``self.psm_modes`` is tried and the result with the
        highest average word confidence is returned.  This handles documents
        with unknown or mixed layouts much better than a single fixed PSM.
        """
        if pytesseract is None:
            raise ImportError("pytesseract is not installed or available.")

        prepared = self._prepare_image(image)

        if self._custom_config:
            text, avg_conf = self._run_tesseract_data(prepared, self._custom_config)
            logger.info(
                "Tesseract OCR (custom config): %d chars, confidence %.1f%%",
                len(text), avg_conf,
            )
            return text, avg_conf

        best_text = ""
        best_conf = 0.0
        best_psm = self.psm_modes[0]

        for psm in self.psm_modes:
            config = get_tesseract_config(psm=psm)
            text, avg_conf = self._run_tesseract_data(prepared, config)

            logger.debug(
                "Tesseract PSM %d: %d chars, confidence %.1f%%",
                psm, len(text), avg_conf,
            )

            if (avg_conf > best_conf) or (
                avg_conf == best_conf and len(text.strip()) > len(best_text.strip())
            ):
                best_text = text
                best_conf = avg_conf
                best_psm = psm

            if best_conf >= TESSERACT_CONFIDENCE_EARLY_EXIT:
                logger.debug(
                    "Tesseract early exit at PSM %d (confidence %.1f%%)",
                    psm,
                    best_conf,
                )
                break

        logger.info(
            "Tesseract multi-PSM winner: PSM %d — %d chars, confidence %.1f%%",
            best_psm, len(best_text), best_conf,
        )
        return best_text, best_conf
