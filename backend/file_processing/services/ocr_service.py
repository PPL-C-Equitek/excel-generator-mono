"""
Multi-stage OCR service.

Pipeline overview (for PDFs):
  1. Attempt direct text extraction (PyPDF2).
  2. If text layer is sufficient ⟶ return immediately.
  3. Convert scanned pages to images at 300 DPI.
  4. Preprocess images (grayscale, denoise, threshold, deskew).
  5. Run Tesseract OCR with --oem 3 / --psm 6.
  6. If average confidence < threshold ⟶ fallback to EasyOCR.
  7. Return structured per-page results.

For standalone images:
  - Run step 4 to 6 directly.
"""

import logging
import re
from typing import Any, Dict, List, Union

from PyPDF2 import PdfReader

from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.ocr.easyocr_engine import EasyOCREngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor
from file_processing.services.ocr_config import (
    CONFIDENCE_THRESHOLD,
    TEXT_LAYER_MIN_CHARS_PER_PAGE,
)

logger = logging.getLogger(__name__)
TextBlock = Union[str, List[List[str]]]


class OCRService:
    """Orchestrates the multi-stage OCR pipeline."""

    THRESHOLD_TEXT_LENGTH = TEXT_LAYER_MIN_CHARS_PER_PAGE

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split *text* on sentence boundaries and newlines."""
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [s.strip() for s in sentences if s.strip()]

    @classmethod
    def _try_easyocr_fallback(cls, image) -> str:
        """Run EasyOCR on a single image and return extracted text.

        Called when Tesseract confidence is below the threshold.
        """
        try:
            engine = EasyOCREngine()
            text, conf = engine.extract_text_with_confidence(image)
            logger.info(
                "EasyOCR fallback: confidence=%.1f%%, chars=%d",
                conf, len(text),
            )
            return text
        except ImportError:
            logger.warning(
                "EasyOCR is not installed; skipping fallback. "
                "Install with: pip install easyocr"
            )
            return ""
        except Exception:
            logger.exception("EasyOCR fallback failed")
            return ""

    @classmethod
    def _ocr_single_image(cls, image, engine: TesseractEngine) -> str:
        """Run OCR on a single image with confidence-based fallback.

        1. Tesseract with preprocessing.
        2. If confidence < threshold → try EasyOCR.
        3. Return whichever produced more text.
        """
        text, confidence = engine.extract_text_with_confidence(image)

        logger.info(
            "Tesseract OCR: confidence=%.1f%%, chars=%d",
            confidence, len(text),
        )

        if confidence < CONFIDENCE_THRESHOLD:
            logger.info(
                "Confidence %.1f%% < threshold %.1f%%; attempting EasyOCR fallback",
                confidence, CONFIDENCE_THRESHOLD,
            )
            fallback_text = cls._try_easyocr_fallback(image)

            if len(fallback_text.strip()) > len(text.strip()):
                logger.info("Using EasyOCR result (%d chars vs Tesseract %d chars)",
                            len(fallback_text), len(text))
                return fallback_text
            else:
                logger.info("Keeping Tesseract result despite low confidence")

        return text

    @classmethod
    def process_pdf_pages(cls, file_path: str, page_numbers: List[int]) -> Dict[str, Any]:
        """Run OCR on specific pages of a PDF.

        Args:
            file_path: Path to the PDF file.
            page_numbers: 1-based page numbers to OCR.

        Returns:
            ``{"content": [{"page": N, "text": [...]}, ...]}``
        """
        logger.info(
            "OCR processing %d specific page(s) from '%s'",
            len(page_numbers), file_path,
        )
        try:
            extractor = PdfOcrExtractor()
            page_images = extractor.convert_pages(file_path, page_numbers=page_numbers)

            engine = TesseractEngine()
            content: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                raw_text = cls._ocr_single_image(image, engine)
                text_blocks = cls.split_sentences(raw_text)

                content.append({"page": page_num, "text": text_blocks})

                logger.info(
                    "Page %d: extracted %d block(s) via OCR", page_num, len(text_blocks),
                )

            return {"content": content}

        except Exception as e:
            logger.exception("OCRService.process_pdf_pages failed")
            raise ValueError(f"OCRService failed to process PDF pages: {str(e)}")

    @classmethod
    def process_pdf(cls, file_path: str) -> Dict[str, Any]:
        """Process a full PDF through the multi-stage pipeline.

        Stage 1 — Direct text extraction (PyPDF2).
        Stage 2 — If text layer is insufficient → OCR with fallback.

        Returns:
            ``{"content": [{"page": N, "text": [...]}, ...]}``
        """
        logger.info("OCR pipeline started for '%s'", file_path)

        try:
            # ---- Stage 1: direct text extraction ----
            reader = PdfReader(file_path)
            content: List[Dict[str, Any]] = []
            extracted_text = ""

            for page_number, page in enumerate(reader.pages, start=1):

                text = page.extract_text() or ""
                extracted_text += text

                sentences = cls.split_sentences(text)

                if sentences:
                    content.append({
                        "page": page_number,
                        "text": sentences,
                    })

            num_pages = len(reader.pages)
            chars_per_page = len(extracted_text.strip()) / num_pages if num_pages > 0 else 0

            logger.info(
                "Stage 1 — text extraction: %d page(s), %d total chars, "
                "%.0f chars/page (threshold=%d)",
                num_pages, len(extracted_text.strip()),
                chars_per_page, cls.THRESHOLD_TEXT_LENGTH,
            )

            if num_pages > 0 and chars_per_page > cls.THRESHOLD_TEXT_LENGTH:
                logger.info(
                    "Text layer is sufficient — returning direct extraction "
                    "(method=PyPDF2, chars=%d)", len(extracted_text.strip()),
                )
                return {"content": content}

            # ---- Stage 2: OCR fallback for scanned PDF ----
            logger.info(
                "Text layer insufficient; switching to OCR pipeline "
                "(method=Tesseract+EasyOCR fallback)",
            )

            extractor = PdfOcrExtractor()
            page_images = extractor.convert_pages(file_path)

            engine = TesseractEngine()
            ocr_content: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                raw_text = cls._ocr_single_image(image, engine)
                text_blocks = cls.split_sentences(raw_text)

                logger.info(
                    "Page %d OCR: %d block(s) extracted",
                    page_num, len(text_blocks),
                )

                ocr_content.append({
                    "page": page_num,
                    "text": text_blocks,
                })

            logger.info(
                "OCR pipeline completed for '%s': %d page(s) processed",
                file_path, len(ocr_content),
            )
            return {"content": ocr_content}

        except Exception as e:
            logger.exception("OCRService.process_pdf failed")
            raise ValueError(f"OCRService failed to process PDF: {str(e)}")

    @classmethod
    def process_image(cls, image) -> Dict[str, Any]:
        """Run OCR on a standalone image (not from a PDF).

        Applies preprocessing and confidence-based fallback.

        Args:
            image: A PIL Image.

        Returns:
            ``{"content": [{"page": 1, "text": [...]}]}``
        """
        logger.info("Processing standalone image via OCR")

        engine = TesseractEngine()
        raw_text = cls._ocr_single_image(image, engine)
        text_blocks = cls.split_sentences(raw_text)

        logger.info("Standalone image OCR: %d block(s) extracted", len(text_blocks))

        return {
            "content": [{
                "page": 1,
                "text": text_blocks,
            }],
        }
