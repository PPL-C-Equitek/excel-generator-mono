from pdf2image import convert_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)

from .ocr.base_ocr_engine import BaseOCREngine


class PdfOcrExtractor:
    def __init__(self, ocr_engine: BaseOCREngine):
        self.ocr_engine = ocr_engine

    def extract(self, file_path: str) -> str:
        extracted_texts = []

        try:
            images = convert_from_path(file_path)

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

        for image in images:
            page_text = self.ocr_engine.extract_text(image)
            extracted_texts.append(page_text)

        return "\n\n".join(extracted_texts).strip()