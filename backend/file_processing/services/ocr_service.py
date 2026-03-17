"""Multi-stage OCR service — EasyOCR primary, line-by-line output.

Pipeline overview (for PDFs):
  1. Attempt direct text extraction (PyPDF2).
  2. If text layer is sufficient ⟶ return immediately (split by newlines).
  3. Convert scanned pages to images at 400 DPI.
  4. Run EasyOCR with spatial line grouping (bounding-box Y-clustering).
  5. If confidence < threshold ⟶ fallback to Tesseract.
  6. Return structured per-page results with line-by-line text.

Output format aligns with NonOCRPDFService: each page's ``"text"`` is a
list of strings — one string per visual line.  No sentence splitting is
performed, which preserves financial data like:
  • Monetary amounts:  Rp 1.000.000 / $1,234.56
  • Abbreviations:     No. 001, Ltd., Inc.
  • Table rows:        Item   Qty   Price   Total
  • Dates:             01.03.2026

For standalone images:
  - Run step 4–5 directly.
"""

import logging
from typing import Any, Dict, List

from PyPDF2 import PdfReader

from file_processing.extractors.ocr.easyocr_engine import EasyOCREngine
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor
from file_processing.services.ocr_config import (
    CONFIDENCE_THRESHOLD,
    TEXT_LAYER_MIN_CHARS_PER_PAGE,
)

logger = logging.getLogger(__name__)

class OCRService:
    """Orchestrates the EasyOCR-primary OCR pipeline."""

    THRESHOLD_TEXT_LENGTH = TEXT_LAYER_MIN_CHARS_PER_PAGE

    @staticmethod
    def split_lines(text: str) -> List[str]:
        """Split *text* on newline boundaries.\n\n        Unlike sentence-based splitting, this preserves financial data\n        (amounts with dots/commas, abbreviations, etc.) and keeps each\n        visual line as a single string.\n        """
        return [line.strip() for line in text.splitlines() if line.strip()]

    @classmethod
    def _try_tesseract_fallback(cls, image) -> str:
        """Run Tesseract (with full preprocessing) on a single image.

        Called when EasyOCR confidence is below the threshold.
        Tesseract uses the heavy pipeline (adaptive thresholding,
        morphological cleanup, deskew, border padding) which can
        sometimes rescue very noisy or low-contrast scans.
        """
        try:
            engine = TesseractEngine(apply_preprocessing=True)
            text, conf = engine.extract_text_with_confidence(image)
            logger.info(
                "Tesseract fallback: confidence=%.1f%%, chars=%d",
                conf, len(text),
            )
            return text
        except ImportError:
            logger.warning(
                "pytesseract is not installed; skipping fallback."
            )
            return ""
        except Exception:
            logger.exception("Tesseract fallback failed")
            return ""

    @classmethod
    def _ocr_single_image(cls, image, engine: EasyOCREngine) -> str:
        """Run OCR on a single image with confidence-based fallback.

        1. EasyOCR with light preprocessing (primary).
        2. If confidence < threshold → try Tesseract with full preprocessing.
        3. Return whichever produced more text.
        """
        text, confidence = engine.extract_text_with_confidence(image)

        logger.info(
            "EasyOCR primary: confidence=%.1f%%, chars=%d",
            confidence, len(text),
        )

        if confidence < CONFIDENCE_THRESHOLD:
            logger.info(
                "Confidence %.1f%% < threshold %.1f%%; attempting Tesseract fallback",
                confidence, CONFIDENCE_THRESHOLD,
            )
            fallback_text = cls._try_tesseract_fallback(image)

            if len(fallback_text.strip()) > len(text.strip()):
                logger.info(
                    "Using Tesseract result (%d chars vs EasyOCR %d chars)",
                    len(fallback_text), len(text),
                )
                return fallback_text
            else:
                logger.info("Keeping EasyOCR result despite low confidence")

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

            engine = EasyOCREngine()
            content: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                raw_text = cls._ocr_single_image(image, engine)
                text_blocks = cls.split_lines(raw_text)

                content.append({"page": page_num, "text": text_blocks})

                logger.info(
                    "Page %d: extracted %d line(s) via OCR", page_num, len(text_blocks),
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

                lines = cls.split_lines(text)

                if lines:
                    content.append({
                        "page": page_number,
                        "text": lines,
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
                "(method=EasyOCR+Tesseract fallback)",
            )

            extractor = PdfOcrExtractor()
            page_images = extractor.convert_pages(file_path)

            engine = EasyOCREngine()
            ocr_content: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                raw_text = cls._ocr_single_image(image, engine)
                text_blocks = cls.split_lines(raw_text)

                logger.info(
                    "Page %d OCR: %d line(s) extracted",
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

        engine = EasyOCREngine()
        raw_text = cls._ocr_single_image(image, engine)
        text_blocks = cls.split_lines(raw_text)

        logger.info("Standalone image OCR: %d line(s) extracted", len(text_blocks))

        return {
            "content": [{
                "page": 1,
                "text": text_blocks,
            }],
        }
