"""
PDF-to-image converter.
"""

import logging
import warnings
from typing import Any, Dict, List, Tuple

from pdf2image import convert_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError,
)

from file_processing.services.ocr_config import PDF_TO_IMAGE_DPI

logger = logging.getLogger(__name__)


class PdfOcrExtractor:
    """Convert PDF pages to PIL Images (no OCR)."""

    def __init__(self, ocr_engine=None, dpi: int | None = None):
        """
        Args:
            ocr_engine: **Deprecated** — ignored. Kept for backward
                        compatibility; will be removed in a future version.
            dpi: Resolution for PDF→image conversion.
                 Defaults to ``PDF_TO_IMAGE_DPI`` from config (300).
        """
        if ocr_engine is not None:
            warnings.warn(
                "ocr_engine parameter is deprecated and ignored. "
                "OCR logic now lives in OCRService.",
                DeprecationWarning,
                stacklevel=2,
            )
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

    def convert_pages(
        self,
        file_path: str,
        page_numbers: List[int] | None = None,
    ) -> List[Tuple[int, Any]]:
        """Convert PDF pages to images.

        Args:
            file_path: Path to the PDF file.
            page_numbers: Optional 1-based page numbers.
                          If ``None``, all pages are converted.

        Returns:
            List of ``(page_number, PIL.Image)`` tuples.
        """
        if page_numbers:
            results: List[Tuple[int, Any]] = []
            for page_num in page_numbers:
                images = self._convert_pages(
                    file_path, first_page=page_num, last_page=page_num,
                )
                if images:
                    results.append((page_num, images[0]))
            logger.info(
                "PdfOcrExtractor: converted %d specific page(s) from '%s' at %d DPI",
                len(results), file_path, self.dpi,
            )
            return results

        images = self._convert_pages(file_path)
        result = [(idx, img) for idx, img in enumerate(images, start=1)]
        logger.info(
            "PdfOcrExtractor: converted %d page(s) from '%s' at %d DPI",
            len(result), file_path, self.dpi,
        )
        return result

    def extract(self, file_path: str) -> str:
        """**Deprecated** — use ``convert_pages()`` + ``OCRService`` instead."""
        warnings.warn(
            "extract() is deprecated. Use convert_pages() and run OCR via OCRService.",
            DeprecationWarning,
            stacklevel=2,
        )
        if self.ocr_engine is None:
            raise RuntimeError("extract() requires an ocr_engine (deprecated path).")

        images = self._convert_pages(file_path)
        extracted_texts = []
        for image in images:
            page_text = self.ocr_engine.extract_text(image)
            extracted_texts.append(page_text)

        return "\n\n".join(extracted_texts).strip()

    def extract_pages(
        self,
        file_path: str,
        page_numbers: List[int] | None = None,
    ) -> List[Dict[str, Any]]:
        """**Deprecated** — use ``convert_pages()`` + ``OCRService`` instead."""
        warnings.warn(
            "extract_pages() is deprecated. Use convert_pages() and run OCR via OCRService.",
            DeprecationWarning,
            stacklevel=2,
        )
        if self.ocr_engine is None:
            raise RuntimeError("extract_pages() requires an ocr_engine (deprecated path).")

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