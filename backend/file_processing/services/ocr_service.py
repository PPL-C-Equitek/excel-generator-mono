from PyPDF2 import PdfReader

from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor

class OCRService:
    THRESHOLD_TEXT_LENGTH = 50 # If the PDF has fewer characters per page on average, treat as scanned.

    @classmethod
    def process_pdf(cls, file_path: str) -> str:
        """
        Determines if a PDF is text-based or scanned.
        Returns extracted text using standard PyPDF2 if text-based, or uses OCR if it is scanned.
        """
        try:
            reader = PdfReader(file_path)
            extracted_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
            
            num_pages = len(reader.pages)
            if num_pages > 0 and len(extracted_text.strip()) / num_pages > cls.THRESHOLD_TEXT_LENGTH:
                return extracted_text.strip()
                
            engine = TesseractEngine()
            extractor = PdfOcrExtractor(ocr_engine=engine)
            return extractor.extract(file_path)
            
        except Exception as e:
            raise ValueError(f"OCRService failed to process PDF: {str(e)}")
