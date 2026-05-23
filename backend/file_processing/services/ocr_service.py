"""Tesseract-based OCR service — line-by-line output for scanned PDFs.

Pipeline overview (for PDFs):
  1. Attempt direct text extraction (PyPDF2).
  2. If text layer is sufficient ⟶ return immediately (split by newlines).
  3. Convert scanned pages to images at 400 DPI.
  4. Run Tesseract with multi-PSM strategy (preprocessing + fallback modes).
  5. Return structured per-page results with line-by-line text.

Output format aligns with NonOCRPDFService: each page's ``"text"`` is a
list of strings — one string per visual line.  No sentence splitting is
performed, which preserves financial data like:
  • Monetary amounts:  Rp 1.000.000 / $1,234.56
  • Abbreviations:     No. 001, Ltd., Inc.
  • Table rows:        Item   Qty   Price   Total
  • Dates:             01.03.2026

For standalone images:
  - Run step 4 directly.
"""

import logging
from typing import Any, Dict, List

from PyPDF2 import PdfReader

from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor
from file_processing.extractors.ocr.ocr_strategy import OCRStrategyFactory
from file_processing.services.ocr_cleanup_service import OCRCleanupService
from file_processing.services.ocr_config import (
    TEXT_LAYER_MIN_CHARS_PER_PAGE,
)

logger = logging.getLogger(__name__)

class OCRService:
    """Orchestrates the Tesseract OCR pipeline."""

    THRESHOLD_TEXT_LENGTH = TEXT_LAYER_MIN_CHARS_PER_PAGE

    @staticmethod
    def split_lines(text: str) -> List[str]:
        """Split *text* on newline boundaries.\n\n        Unlike sentence-based splitting, this preserves financial data\n        (amounts with dots/commas, abbreviations, etc.) and keeps each\n        visual line as a single string.\n        """
        return [line.strip() for line in text.splitlines() if line.strip()]

    @classmethod
    def _ocr_single_image(cls, image) -> str:
        """Run Tesseract OCR on a single image.

        Uses multi-PSM strategy for robust handling of various document layouts.
        """
        return cls._ocr_single_image_with_metadata(image)["text"]

    @classmethod
    def _ocr_single_image_with_metadata(cls, image) -> Dict[str, Any]:
        """Run Tesseract OCR and return text plus word-level metadata."""
        try:
            engine = TesseractEngine(apply_preprocessing=True)
            metadata = engine.extract_text_with_metadata(image)
            logger.info(
                "Tesseract OCR: confidence=%.1f%%, chars=%d",
                metadata.get("avg_confidence", 0.0), len(metadata.get("text", "")),
            )
            return metadata
        except ImportError as exc:
            logger.warning(
                "pytesseract is not installed; cannot perform OCR."
            )
            raise ValueError(
                "OCR dependency error: pytesseract or Tesseract is not available."
            ) from exc
        except Exception as exc:
            logger.exception("Tesseract OCR failed")
            raise ValueError(f"OCR runtime error: {str(exc)}") from exc

    @staticmethod
    def _build_page_metadata(cleanup_result: Dict[str, Any], page_num: int) -> Dict[str, Any]:
        metadata = dict(cleanup_result.get("ocr_metadata", {}))
        metadata.setdefault("page", page_num)
        return metadata

    @staticmethod
    def _build_document_metadata(page_metadata: List[Dict[str, Any]], document_type: str) -> Dict[str, Any]:
        return OCRCleanupService.summarize_page_metadata(page_metadata, document_type)

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

            content: List[Dict[str, Any]] = []
            page_metadata: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                ocr_payload = cls._ocr_single_image_with_metadata(image)
                cleanup_result = OCRStrategyFactory.cleanup_text_for_document(
                    document_type="pdf",
                    text=ocr_payload.get("text", ""),
                    avg_confidence=float(ocr_payload.get("avg_confidence", 0.0)),
                    word_details=ocr_payload.get("word_details"),
                )
                text_blocks = cls.split_lines(cleanup_result["text"])

                page_entry = {
                    "page": page_num,
                    "text": text_blocks,
                    "ocr_metadata": cls._build_page_metadata(cleanup_result, page_num),
                }
                content.append(page_entry)
                page_metadata.append(page_entry["ocr_metadata"])

                logger.info(
                    "Page %d: extracted %d line(s) via OCR", page_num, len(text_blocks),
                )

            return {
                "content": content,
                "ocr_metadata": cls._build_document_metadata(page_metadata, "pdf"),
            }

        except Exception as e:
            logger.exception("OCRService.process_pdf_pages failed")
            raise ValueError(f"OCRService failed to process PDF pages: {str(e)}")

    @classmethod
    def process_pdf(cls, file_path: str) -> Dict[str, Any]:
        """Process a full PDF through the multi-stage pipeline.

        Stage 1 — Direct text extraction (PyPDF2).
        Stage 2 — If text layer is insufficient → OCR with Tesseract.

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
                "(method=Tesseract multi-PSM)",
            )

            extractor = PdfOcrExtractor()
            page_images = extractor.convert_pages(file_path)

            ocr_content: List[Dict[str, Any]] = []
            page_metadata: List[Dict[str, Any]] = []

            for page_num, image in page_images:
                ocr_payload = cls._ocr_single_image_with_metadata(image)
                cleanup_result = OCRStrategyFactory.cleanup_text_for_document(
                    document_type="pdf",
                    text=ocr_payload.get("text", ""),
                    avg_confidence=float(ocr_payload.get("avg_confidence", 0.0)),
                    word_details=ocr_payload.get("word_details"),
                )
                text_blocks = cls.split_lines(cleanup_result["text"])

                logger.info(
                    "Page %d OCR: %d line(s) extracted",
                    page_num, len(text_blocks),
                )

                page_entry = {
                    "page": page_num,
                    "text": text_blocks,
                    "ocr_metadata": cls._build_page_metadata(cleanup_result, page_num),
                }
                ocr_content.append(page_entry)
                page_metadata.append(page_entry["ocr_metadata"])

            logger.info(
                "OCR pipeline completed for '%s': %d page(s) processed",
                file_path, len(ocr_content),
            )
            return {
                "content": ocr_content,
                "ocr_metadata": cls._build_document_metadata(page_metadata, "pdf"),
            }

        except Exception as e:
            logger.exception("OCRService.process_pdf failed")
            raise ValueError(f"OCRService failed to process PDF: {str(e)}")

    @classmethod
    def process_image(cls, image) -> Dict[str, Any]:
        """Run OCR on a standalone image (not from a PDF).

        Applies Tesseract OCR and returns line-based output.

        Args:
            image: A PIL Image.

        Returns:
            ``{"content": [{"page": 1, "text": [...]}]}``
        """
        logger.info("Processing standalone image via OCR")

        ocr_payload = cls._ocr_single_image_with_metadata(image)
        cleanup_result = OCRStrategyFactory.cleanup_text_for_document(
            document_type="image",
            text=ocr_payload.get("text", ""),
            avg_confidence=float(ocr_payload.get("avg_confidence", 0.0)),
            word_details=ocr_payload.get("word_details"),
        )
        text_blocks = cls.split_lines(cleanup_result["text"])

        logger.info("Standalone image OCR: %d line(s) extracted", len(text_blocks))

        return {
            "content": [{
                "page": 1,
                "text": text_blocks,
                "ocr_metadata": cls._build_page_metadata(cleanup_result, 1),
            }],
            "ocr_metadata": cls._build_document_metadata([
                cls._build_page_metadata(cleanup_result, 1)
            ], "image"),
        }
