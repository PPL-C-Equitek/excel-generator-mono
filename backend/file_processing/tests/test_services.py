import os
import tempfile
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase
from reportlab.pdfgen import canvas

from file_processing.services.non_ocr_pdf_service import NonOCRPDFService
from file_processing.services.ocr_service import OCRService


extract_non_ocr_pdf_to_json = NonOCRPDFService.extract_non_ocr_pdf_to_json


class TestOCRService(SimpleTestCase):
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


class TestNonOCRPDFService(SimpleTestCase):
    """Tests designed around text/table/blank/error input partitions."""

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
        self.addCleanup(self._remove_temp_file, tmp.name)
        return tmp.name

    def _remove_temp_file(self, path: str):
        if os.path.exists(path):
            os.unlink(path)

    def _stub_pdfplumber_open(self, mock_open, pages):
        mock_pdf = MagicMock()
        mock_pdf.pages = pages

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_pdf
        mock_context.__exit__.return_value = None

        mock_open.return_value = mock_context
        return mock_pdf

    def _make_plain_text_page(self, text):
        page = MagicMock()
        page.extract_tables.return_value = []
        page.extract_text.return_value = text
        return page

    @patch("file_processing.services.non_ocr_pdf_service.pdfplumber.open")
    def test_plain_text_page_splits_lines(self, mock_open):
        text_page = self._make_plain_text_page("Hello World\nSecond Line")
        self._stub_pdfplumber_open(mock_open, [text_page])

        result = extract_non_ocr_pdf_to_json("text.pdf")

        self.assertEqual(
            result,
            {"content": [{"page": 1, "text": ["Hello World", "Second Line"]}]},
        )
        mock_open.assert_called_once_with("text.pdf")
        text_page.extract_tables.assert_called_once()
        text_page.extract_text.assert_called_once()
        text_page.find_tables.assert_not_called()

    def test_real_pdf_text_pages_are_extracted_in_order(self):
        path = self._create_pdf(["Page one", "Page two", "Page three"])

        result = extract_non_ocr_pdf_to_json(path)

        self.assertEqual(
            result,
            {
                "content": [
                    {"page": 1, "text": ["Page one"]},
                    {"page": 2, "text": ["Page two"]},
                    {"page": 3, "text": ["Page three"]},
                ]
            },
        )

    @patch("file_processing.services.non_ocr_pdf_service.pdfplumber.open")
    def test_blank_text_partitions_return_empty_lists(self, mock_open):
        for raw_text in ("", None):
            with self.subTest(raw_text=raw_text):
                blank_page = self._make_plain_text_page(raw_text)
                self._stub_pdfplumber_open(mock_open, [blank_page])

                result = extract_non_ocr_pdf_to_json("blank.pdf")

                self.assertEqual(result, {"content": [{"page": 1, "text": []}]})
                blank_page.find_tables.assert_not_called()
                mock_open.reset_mock()

    @patch("file_processing.services.non_ocr_pdf_service.pdfplumber.open")
    def test_table_rows_are_normalized_and_outside_text_appended_after_rows(
        self, mock_open
    ):
        first_table_region = MagicMock()
        first_table_region.bbox = (0, 0, 50, 50)
        second_table_region = MagicMock()
        second_table_region.bbox = (50, 0, 100, 50)

        filtered_once_page = MagicMock()
        filtered_twice_page = MagicMock()
        filtered_twice_page.extract_text.return_value = (
            "Outside table line\n\n  Trimmed outside line  "
        )

        table_page = MagicMock()
        table_page.extract_tables.return_value = [
            [["Name", None], ["Alice", "123"]],
            [["Course"], ["Testing"]],
        ]
        table_page.find_tables.return_value = [first_table_region, second_table_region]
        table_page.outside_bbox.return_value = filtered_once_page
        filtered_once_page.outside_bbox.return_value = filtered_twice_page
        self._stub_pdfplumber_open(mock_open, [table_page])

        result = extract_non_ocr_pdf_to_json("table.pdf")

        self.assertEqual(
            result,
            {
                "content": [
                    {
                        "page": 1,
                        "text": [
                            ["Name", ""],
                            ["Alice", "123"],
                            ["Course"],
                            ["Testing"],
                            "Outside table line",
                            "Trimmed outside line",
                        ],
                    }
                ]
            },
        )
        table_page.outside_bbox.assert_called_once_with(first_table_region.bbox)
        filtered_once_page.outside_bbox.assert_called_once_with(
            second_table_region.bbox
        )
        filtered_twice_page.extract_text.assert_called_once()
        table_page.extract_text.assert_not_called()

    @patch("file_processing.services.non_ocr_pdf_service.pdfplumber.open")
    def test_mixed_page_partitions_preserve_page_numbers_and_shape(self, mock_open):
        text_page = self._make_plain_text_page("Alpha\nBeta")
        blank_page = self._make_plain_text_page("")

        table_region = MagicMock()
        table_region.bbox = (0, 0, 100, 100)
        filtered_page = MagicMock()
        filtered_page.extract_text.return_value = ""
        table_page = MagicMock()
        table_page.extract_tables.return_value = [[["Header"], ["Value"]]]
        table_page.find_tables.return_value = [table_region]
        table_page.outside_bbox.return_value = filtered_page
        self._stub_pdfplumber_open(mock_open, [text_page, table_page, blank_page])

        result = extract_non_ocr_pdf_to_json("mixed.pdf")

        self.assertEqual(
            result,
            {
                "content": [
                    {"page": 1, "text": ["Alpha", "Beta"]},
                    {"page": 2, "text": [["Header"], ["Value"]]},
                    {"page": 3, "text": []},
                ]
            },
        )

    @patch("file_processing.services.non_ocr_pdf_service.pdfplumber.open")
    def test_pdfplumber_errors_are_propagated(self, mock_open):
        mock_open.side_effect = ValueError("corrupt PDF")

        with self.assertRaisesRegex(ValueError, "corrupt PDF"):
            extract_non_ocr_pdf_to_json("corrupt.pdf")

        mock_open.assert_called_once_with("corrupt.pdf")

    def test_missing_pdf_path_raises_file_not_found(self):
        missing_path = "/tmp/nonexistent_file_12345.pdf"
        self.assertFalse(os.path.exists(missing_path))

        with self.assertRaises(FileNotFoundError):
            extract_non_ocr_pdf_to_json(missing_path)
