import os
import tempfile
from django.test import TestCase
from unittest.mock import patch, MagicMock

from file_processing.services.ocr_service import OCRService
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from file_processing.services.non_ocr_pdf_service import NonOCRPDFService


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
        self.assertEqual(len(result["content"][0]["text"]), 3)

    @patch("file_processing.services.ocr_service.OCRService._ocr_single_image")
    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    @patch("file_processing.services.ocr_service.PdfReader")
    def test_scanned_pdf_uses_ocr(self, mock_reader, mock_extractor_cls, mock_ocr_single):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_reader.return_value.pages = [mock_page]

        mock_image = MagicMock()
        mock_extractor_cls.return_value.convert_pages.return_value = [(1, mock_image)]

        mock_ocr_single.return_value = "OCR sentence one. OCR sentence two."

        result = OCRService.process_pdf("dummy.pdf")

        self.assertEqual(result["content"][0]["page"], 1)
        self.assertGreater(len(result["content"][0]["text"]), 0)
        mock_ocr_single.assert_called_once()

    @patch("file_processing.services.ocr_service.PdfReader")
    def test_exception_wrapping(self, mock_reader):

        mock_reader.side_effect = Exception("boom")

        with self.assertRaises(ValueError) as context:
            OCRService.process_pdf("bad.pdf")

        self.assertIn("OCRService failed", str(context.exception))

    def test_split_sentences_basic(self):
        text = "Hello world. How are you?\nFine."

        result = OCRService.split_sentences(text)

        self.assertEqual(
            result,
            ["Hello world.", "How are you?", "Fine."]
        )

    @patch("file_processing.services.ocr_service.OCRService._ocr_single_image")
    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    def test_process_pdf_pages_success(self, mock_extractor_cls, mock_ocr_single):

        mock_image = MagicMock()
        mock_extractor_cls.return_value.convert_pages.return_value = [(1, mock_image)]

        mock_ocr_single.return_value = "Hello OCR from single image"

        result = OCRService.process_pdf_pages("/tmp/file.pdf", [1])

        self.assertEqual(result["content"][0]["page"], 1)
        self.assertEqual(result["content"][0]["text"], ["Hello OCR from single image"])

    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    def test_process_pdf_pages_no_images(self, mock_extractor_cls):

        mock_extractor_cls.return_value.convert_pages.return_value = []

        result = OCRService.process_pdf_pages("/tmp/file.pdf", [1])

        self.assertEqual(result["content"], [])

    @patch("file_processing.services.ocr_service.EasyOCREngine")
    def test_try_easyocr_fallback_success(self, mock_easyocr):
        mock_engine = MagicMock()
        mock_engine.extract_text_with_confidence.return_value = ("Fallback text", 60.0)
        mock_easyocr.return_value = mock_engine

        text = OCRService._try_easyocr_fallback("mock_image")

        self.assertEqual(text, "Fallback text")


    @patch("file_processing.services.ocr_service.OCRService._try_easyocr_fallback")
    def test_ocr_single_image_high_confidence(self, mock_fallback):
        engine = MagicMock()
        engine.extract_text_with_confidence.return_value = ("Tesseract is confident", 85.0)

        text = OCRService._ocr_single_image("image", engine)

        self.assertEqual(text, "Tesseract is confident")
        mock_fallback.assert_not_called()

    @patch("file_processing.services.ocr_service.OCRService._try_easyocr_fallback")
    def test_ocr_single_image_low_confidence_fallback_better(self, mock_fallback):
        engine = MagicMock()
        engine.extract_text_with_confidence.return_value = ("t3ss3r4ct is bad.", 25.0)

        mock_fallback.return_value = "EasyOCR is much better here."

        text = OCRService._ocr_single_image("image", engine)

        self.assertEqual(text, "EasyOCR is much better here.")
        mock_fallback.assert_called_once_with("image")

    @patch("file_processing.services.ocr_service.OCRService._ocr_single_image")
    def test_process_image_success(self, mock_ocr_single):
        mock_ocr_single.return_value = "Standalone image OCR"

        result = OCRService.process_image("mock_image")

        self.assertEqual(result["content"][0]["page"], 1)
        self.assertEqual(result["content"][0]["text"], ["Standalone image OCR"])

    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    def test_process_pdf_pages_exception(self, mock_extractor_cls):

        mock_extractor_cls.return_value.convert_pages.side_effect = Exception("fail")

        with self.assertRaises(ValueError):
            OCRService.process_pdf_pages("/tmp/file.pdf", [1])

    @patch("file_processing.services.ocr_service.PdfReader")
    def test_process_pdf_text_based(self, mock_reader):

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello world " * 20

        mock_reader.return_value.pages = [mock_page]

        result = OCRService.process_pdf("/tmp/file.pdf")

        self.assertEqual(result["content"][0]["page"], 1)

    @patch("file_processing.services.ocr_service.OCRService._ocr_single_image")
    @patch("file_processing.services.ocr_service.PdfOcrExtractor")
    @patch("file_processing.services.ocr_service.PdfReader")
    def test_process_pdf_ocr_branch(self, mock_reader, mock_extractor_cls, mock_ocr_single):

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_reader.return_value.pages = [mock_page]

        mock_image = MagicMock()
        mock_extractor_cls.return_value.convert_pages.return_value = [(1, mock_image)]

        mock_ocr_single.return_value = "OCR TEXT"

        result = OCRService.process_pdf("/tmp/file.pdf")

        self.assertEqual(result["content"][0]["text"], ["OCR TEXT"])


class TestNonOCRPDFService(TestCase):
    """Tests covering extract_pdf_to_json."""

    def _create_pdf(self, texts: list[str]) -> str:
        """Create a real PDF with one page per text entry and return its path."""
        buf = BytesIO()
        p = canvas.Canvas(buf)
        for text in texts:
            p.drawString(72, 720, text)
            p.showPage()
        p.save()
        buf.seek(0)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(buf.read())
        tmp.close()
        return tmp.name

    def _create_blank_pdf(self) -> str:
        """Create a PDF whose page returns empty text."""
        buf = BytesIO()
        p = canvas.Canvas(buf)
        p.showPage()
        p.save()
        buf.seek(0)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(buf.read())
        tmp.close()
        return tmp.name

    def _create_table_pdf(self) -> str:
        """Create a PDF containing a table (triggers table-extraction path)."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        data = [
            ["NAMA", "NPM", "SEMESTER"],
            ["Alice", "123", "6"],
            ["Bob", "456", "4"],
        ]
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        doc.build([table])
        return tmp.name

    def _create_table_with_none_cell_pdf(self) -> str:
        """Create a table PDF where a cell is empty (None → '')."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        data = [
            ["COL1", "COL2"],
            ["val", ""],
        ]
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
        doc.build([table])
        return tmp.name

    def _create_table_plus_text_pdf(self) -> str:
        """Create a PDF with a table AND plain text below it."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        styles = getSampleStyleSheet()

        data = [
            ["NAMA", "NPM"],
            ["Alice", "123"],
        ]
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))

        text_paragraph = Paragraph(
            "Please ignore this. THIS IS ONLY FOR TESTING.", styles["Normal"]
        )

        doc.build([table, Spacer(1, 20), text_paragraph])
        return tmp.name

    def test_single_page_text_returns_lines(self):
        """Plain-text page → text is a list of line strings."""
        path = self._create_pdf(["Hello World"])
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            self.assertEqual(len(result["content"]), 1)
            self.assertEqual(result["content"][0]["page"], 1)

            text = result["content"][0]["text"]
            self.assertIsInstance(text, list)
            joined = " ".join(text) if isinstance(text[0], str) else str(text)
            self.assertIn("Hello World", joined)
        finally:
            os.unlink(path)

    def test_multi_page_pdf(self):
        """Covers loop iteration for multiple pages."""
        path = self._create_pdf(["Page one", "Page two", "Page three"])
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            self.assertEqual(len(result["content"]), 3)
            for i, entry in enumerate(result["content"], start=1):
                self.assertEqual(entry["page"], i)
                self.assertIsInstance(entry["text"], list)
        finally:
            os.unlink(path)

    def test_blank_page_returns_empty_list(self):
        """Covers the branch when page has no text and no tables."""
        path = self._create_blank_pdf()
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            self.assertEqual(result["content"][0]["text"], [])
        finally:
            os.unlink(path)

    def test_table_pdf_returns_rows(self):
        """Pages with tables → text is list of row-arrays."""
        path = self._create_table_pdf()
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            text = result["content"][0]["text"]
            self.assertIsInstance(text, list)
            self.assertGreaterEqual(len(text), 3)
            for row in text:
                self.assertIsInstance(row, list)
            self.assertIn("NAMA", text[0])
            self.assertIn("NPM", text[0])
        finally:
            os.unlink(path)

    def test_table_none_cell_replaced_with_empty_string(self):
        """None cells in tables are replaced with empty strings."""
        path = self._create_table_with_none_cell_pdf()
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            text = result["content"][0]["text"]
            for row in text:
                if isinstance(row, list):
                    for cell in row:
                        self.assertIsNotNone(cell)
                        self.assertIsInstance(cell, str)
        finally:
            os.unlink(path)

    def test_table_plus_outside_text(self):
        """Text outside table area is also captured as plain strings."""
        path = self._create_table_plus_text_pdf()
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            text = result["content"][0]["text"]

            table_rows = [e for e in text if isinstance(e, list)]
            plain_lines = [e for e in text if isinstance(e, str)]

            self.assertGreaterEqual(len(table_rows), 2)
            self.assertGreaterEqual(len(plain_lines), 1)
            combined = " ".join(plain_lines)
            self.assertIn("TESTING", combined)
        finally:
            os.unlink(path)

    def test_corrupt_file_raises_exception(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(b"not a pdf at all")
        tmp.close()
        try:
            with self.assertRaises(Exception):
                NonOCRPDFService.extract_non_ocr_pdf_to_json(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_nonexistent_file_raises_exception(self):
        with self.assertRaises(Exception):
            NonOCRPDFService.extract_non_ocr_pdf_to_json("/tmp/nonexistent_file_12345.pdf")

    def test_return_structure_keys(self):
        path = self._create_pdf(["structure test"])
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            self.assertIn("content", result)
            self.assertIsInstance(result["content"], list)
        finally:
            os.unlink(path)

    def test_content_entry_keys(self):
        path = self._create_pdf(["key test"])
        try:
            result = NonOCRPDFService.extract_non_ocr_pdf_to_json(path)
            for entry in result["content"]:
                self.assertIn("page", entry)
                self.assertIn("text", entry)
        finally:
            os.unlink(path)
