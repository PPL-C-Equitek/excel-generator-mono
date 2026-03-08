from pdf2image import convert_from_path
from .ocr.base_ocr_engine import BaseOCREngine

class PdfOcrExtractor:
    def __init__(self, ocr_engine: BaseOCREngine):
        self.ocr_engine = ocr_engine

    def extract(self, file_path: str) -> str:
        if convert_from_path is None:
            raise ImportError("pdf2image is not installed or available.")

        extracted_texts = []
        
        try:
            images = convert_from_path(file_path)
        except Exception as e:
            raise ValueError(f"Corrupted or unreadable PDF '{file_path}': {e}")
        
        for image in images:
            page_text = self.ocr_engine.extract_text(image)
            extracted_texts.append(page_text)
            
        return "\n\n".join(extracted_texts).strip()
