import os
from unittest import TestCase
from unittest.mock import patch, MagicMock

from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor

class DummyOCREngine(BaseOCREngine):
    def __init__(self, text_to_return=""):
        self.text_to_return = text_to_return

    def extract_text(self, image) -> str:
        return self.text_to_return


class TestPdfOcrExtractor(TestCase):
    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_ocr_extracts_text_from_scanned_pdf(self, mock_convert):
        mock_convert.return_value = [MagicMock()]
        
        engine = DummyOCREngine(text_to_return="Sample Scanned Text")
        extractor = PdfOcrExtractor(ocr_engine=engine)
        
        extracted_text = extractor.extract("dummy_scanned_path.pdf")
        
        self.assertIn("Sample Scanned Text", extracted_text)
        mock_convert.assert_called_once_with("dummy_scanned_path.pdf")

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_multiple_pages_ocr(self, mock_convert):
        mock_convert.return_value = [MagicMock(), MagicMock(), MagicMock()]
        
        class MultiPageDummyEngine(BaseOCREngine):
            def __init__(self):
                self.page_count = 0
            
            def extract_text(self, image) -> str:
                self.page_count += 1
                return f"Text from page {self.page_count}"

        engine = MultiPageDummyEngine()
        extractor = PdfOcrExtractor(ocr_engine=engine)
        
        extracted_text = extractor.extract("dummy_multi_page.pdf")
        
        self.assertIn("Text from page 1", extracted_text)
        self.assertIn("Text from page 2", extracted_text)
        self.assertIn("Text from page 3", extracted_text)
        mock_convert.assert_called_once_with("dummy_multi_page.pdf")

    def test_ocr_engine_abstraction(self):
        mock_engine = MagicMock(spec=BaseOCREngine)
        mock_engine.extract_text.return_value = "Mocked Text"
        
        extractor = PdfOcrExtractor(ocr_engine=mock_engine)
        self.assertIs(extractor.ocr_engine, mock_engine)
        
    def test_accuracy_threshold(self):
        from file_processing.utils.metrics import calculate_accuracy
        
        ground_truth = "Hello World"
        extracted = "Hello W0rld"
        
        acc = calculate_accuracy(ground_truth, extracted)
        self.assertGreaterEqual(acc, 0.90)
        
        bad_extracted = "Hxlzo"
        bad_acc = calculate_accuracy(ground_truth, bad_extracted)
        self.assertLess(bad_acc, 0.90)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_error_handling_corrupted_pdf(self, mock_convert):
        mock_convert.side_effect = Exception("Unable to get page count.")
        
        engine = DummyOCREngine()
        extractor = PdfOcrExtractor(ocr_engine=engine)
        
        with self.assertRaises(ValueError) as context:
            extractor.extract("corrupted.pdf")
            
        self.assertIn("corrupt", str(context.exception).lower())
