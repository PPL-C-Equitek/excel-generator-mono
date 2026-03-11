import re
from PyPDF2 import PdfReader
from typing import Dict, Any

from pdf2image import convert_from_path

from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor

class OCRService:
    THRESHOLD_TEXT_LENGTH = 50 # If the PDF has fewer characters per page on average, treat as scanned.

    @staticmethod
    def split_sentences(text: str):
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [s.strip() for s in sentences if s.strip()]

    @classmethod
    def process_pdf_pages(cls, file_path: str, page_numbers: list[int]) -> Dict[str, Any]:
        """
        Run OCR on specific pages of a PDF.

        Args:
            file_path: Path to PDF file.
            page_numbers: 1-based page numbers to OCR.

        Returns:
            dict matching NonOCR schema: {"content": [{"page": N, "text": [...]}, ...]}
        """
        try:
            engine = TesseractEngine()
            content = []

            for page_num in page_numbers:
                images = convert_from_path(
                    file_path, first_page=page_num, last_page=page_num
                )
                if images:
                    page_text = engine.extract_text(images[0])
                    lines = cls.split_sentences(page_text)
                else:
                    lines = []

                content.append({
                    "page": page_num,
                    "text": lines,
                })

            return {"content": content}

        except Exception as e:
            raise ValueError(f"OCRService failed to process PDF pages: {str(e)}")

    @classmethod
    def process_pdf(cls, file_path: str) -> Dict[str, Any]:
        """
        Determines if a PDF is text-based or scanned.
        Returns extracted text using standard PyPDF2 if text-based, or uses OCR if it is scanned.
        """
        try:
            reader = PdfReader(file_path)
            content = []

            extracted_text = ""

            for page_number, page in enumerate(reader.pages, start=1):

                text = page.extract_text() or ""
                extracted_text += text

                lines = cls.split_sentences(text)

                if lines:
                    content.append({
                        "page": page_number,
                        "type": "text",
                        "lines": lines
                    })

            num_pages = len(reader.pages)

            if num_pages > 0 and len(extracted_text.strip()) / num_pages > cls.THRESHOLD_TEXT_LENGTH:
                return {"content": content}

            engine = TesseractEngine()
            extractor = PdfOcrExtractor(ocr_engine=engine)

            ocr_text = extractor.extract(file_path)

            lines = cls.split_sentences(ocr_text)

            return {
                "content": [
                    {
                        "page": 1,
                        "type": "text",
                        "lines": lines
                    }
                ]
            }

        except Exception as e:
            raise ValueError(f"OCRService failed to process PDF: {str(e)}")
