"""
PDF OCR extractor — converts PDF pages to images and runs OCR.
"""

import logging
from typing import Any, Dict, List

from pdf2image import convert_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError,
)

from .ocr.base_ocr_engine import BaseOCREngine
from file_processing.services.ocr_config import PDF_TO_IMAGE_DPI

logger = logging.getLogger(__name__)


class PdfOcrExtractor:
    """Convert PDF pages to images then delegate to an OCR engine."""

    def __init__(self, ocr_engine: BaseOCREngine, dpi: int | None = None):
        """
        Args:
            ocr_engine: Any ``BaseOCREngine`` implementation.
            dpi: Resolution for PDF→image conversion.
                 Defaults to ``PDF_TO_IMAGE_DPI`` from config (300).
        """
        self.ocr_engine = ocr_engine
        self.dpi = dpi or PDF_TO_IMAGE_DPI

    def _convert_pages(self, file_path: str, **kwargs) -> list:
        """Wrap ``convert_from_path`` with consistent error handling."""
        try:
            return convert_from_path(file_path, dpi=self.dpi, **kwargs)

        except PDFInfoNotInstalledError as e:
            raise RuntimeError(
                "Poppler is not installed or not available in PATH."
            ) from e

        except (PDFPageCountError, PDFSyntaxError) as e:
            raise ValueError(
                f"Corrupted or unreadable PDF '{file_path}'"
            ) from e

        except Exception as e:
            raise RuntimeError(
                f"Unexpected error while converting PDF '{file_path}': {e}"
            ) from e

    def extract(self, file_path: str) -> str:
        """Legacy API: return all OCR text as a single string."""
        images = self._convert_pages(file_path)
        extracted_texts = []
        for image in images:
            page_text = self.ocr_engine.extract_text(image)
            extracted_texts.append(page_text)

        return "\n\n".join(extracted_texts).strip()

    def extract_pages(self, file_path: str,
                      page_numbers: List[int] | None = None
                      ) -> List[Dict[str, Any]]:
        """Return per-page OCR results as structured data.

        Args:
            file_path: Path to the PDF.
            page_numbers: Optional 1-based page numbers to OCR.
                          If ``None``, all pages are processed.

        Returns:
            List of dicts: ``[{"page": N, "text": "...", "confidence": F}, ...]``
        """
        results: List[Dict[str, Any]] = []

        if page_numbers:
            for page_num in page_numbers:
                images = self._convert_pages(
                    file_path, first_page=page_num, last_page=page_num,
                )
                if images:
                    text, conf = self.ocr_engine.extract_text_with_confidence(images[0])
                else:
                    text, conf = "", 0.0

                results.append({
                    "page": page_num,
                    "text": text,
                    "confidence": conf,
                })
        else:
            images = self._convert_pages(file_path)
            for idx, image in enumerate(images, start=1):
                text, conf = self.ocr_engine.extract_text_with_confidence(image)
                results.append({
                    "page": idx,
                    "text": text,
                    "confidence": conf,
                })

        logger.info(
            "PdfOcrExtractor: processed %d page(s) from '%s' at %d DPI",
            len(results), file_path, self.dpi,
        )
        return results