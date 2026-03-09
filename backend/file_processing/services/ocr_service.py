import re
from PyPDF2 import PdfReader
from typing import Dict, Any

from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor

class OCRService:
    THRESHOLD_TEXT_LENGTH = 50 # If the PDF has fewer characters per page on average, treat as scanned.

    @staticmethod
    def split_sentences(text: str):
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [s.strip() for s in sentences if s.strip()]

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
