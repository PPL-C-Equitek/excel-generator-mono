from typing import Any
import pytesseract

from .base_ocr_engine import BaseOCREngine

class TesseractEngine(BaseOCREngine):
    def extract_text(self, image: Any) -> str:
        if pytesseract is None:
            raise ImportError("pytesseract is not installed or available.")
        
        return pytesseract.image_to_string(image)
