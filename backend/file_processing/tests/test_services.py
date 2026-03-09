from django.test import TestCase
from unittest.mock import patch, MagicMock

from file_processing.services.ocr_service import OCRService


class TestOCRService(TestCase):

    @patch("file_processing.services.ocr_service.PdfReader")
    def test_text_pdf_path(self, mock_reader):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = (
            "Hello world. Second sentence. "
            "This is a long enough text to pass the OCR threshold detection."
        )

        mock_reader.return_value.pages = [mock_page]

        result = OCRService.process_pdf("dummy.pdf")

        self.assertIn("content", result)
        self.assertEqual(result["content"][0]["page"], 1)
        self.assertEqual(len(result["content"][0]["lines"]), 3)

    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    @patch("file_processing.services.ocr_service.TesseractEngine")
    @patch("file_processing.services.ocr_service.PdfReader")
    def test_scanned_pdf_uses_ocr(self, mock_reader, mock_engine, mock_extractor):

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_reader.return_value.pages = [mock_page]

        extractor_instance = MagicMock()
        extractor_instance.extract.return_value = "OCR sentence one. OCR sentence two."
        mock_extractor.return_value = extractor_instance

        result = OCRService.process_pdf("dummy.pdf")

        self.assertEqual(result["content"][0]["page"], 1)
        self.assertGreater(len(result["content"][0]["lines"]), 0)

    @patch("file_processing.services.ocr_service.PdfReader")
    def test_exception_wrapping(self, mock_reader):

        mock_reader.side_effect = Exception("boom")

        with self.assertRaises(ValueError) as context:
            OCRService.process_pdf("bad.pdf")

        self.assertIn("OCRService failed", str(context.exception))