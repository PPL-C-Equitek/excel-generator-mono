import os
import tempfile
import builtins

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock, PropertyMock
from PyPDF2.errors import PdfReadError
from openpyxl import Workbook

from file_processing.services.ocr_service import OCRService
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from file_processing.services.non_ocr_pdf_service import NonOCRPDFService

from file_processing.services.upload_service import (
    _get_empty_page_numbers,
    _has_zip_signature,
    _is_legacy_xls_content,
    _is_ole_container,
    validate_pdf,
)


class TestOCRService(TestCase):
    @patch("file_processing.services.ocr_service.PdfReader")
    def test_text_pdf_path(self, mock_reader):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = (
            "Hello world\nSecond line\n"
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

        mock_ocr_single.return_value = "OCR line one\nOCR line two"

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

    def test_split_lines_basic(self):
        text = "Hello world. How are you?\nFine.\nRp 1.000.000"

        result = OCRService.split_lines(text)

        self.assertEqual(
            result,
            ["Hello world. How are you?", "Fine.", "Rp 1.000.000"]
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

    @patch("file_processing.services.ocr_service.TesseractEngine")
    def test_try_tesseract_fallback_success(self, mock_tesseract):
        mock_engine = MagicMock()
        mock_engine.extract_text_with_confidence.return_value = ("Fallback text", 60.0)
        mock_tesseract.return_value = mock_engine

        text = OCRService._try_tesseract_fallback("mock_image")

        self.assertEqual(text, "Fallback text")


    @patch("file_processing.services.ocr_service.OCRService._try_tesseract_fallback")
    def test_ocr_single_image_high_confidence(self, mock_fallback):
        engine = MagicMock()
        engine.extract_text_with_confidence.return_value = ("EasyOCR is confident", 85.0)

        text = OCRService._ocr_single_image("image", engine)

        self.assertEqual(text, "EasyOCR is confident")
        mock_fallback.assert_not_called()

    @patch("file_processing.services.ocr_service.OCRService._try_tesseract_fallback")
    def test_ocr_single_image_low_confidence_fallback_better(self, mock_fallback):
        engine = MagicMock()
        engine.extract_text_with_confidence.return_value = ("e4sy0cr is bad.", 25.0)

        mock_fallback.return_value = "Tesseract is much better here."

        text = OCRService._ocr_single_image("image", engine)

        self.assertEqual(text, "Tesseract is much better here.")
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

    @patch("file_processing.services.ocr_service.TesseractEngine")
    def test_try_tesseract_fallback_import_error(self, mock_tesseract):
        mock_tesseract.side_effect = ImportError()

        result = OCRService._try_tesseract_fallback("img")

        self.assertEqual(result, "")

    @patch("file_processing.services.ocr_service.OCRService._try_tesseract_fallback")
    def test_ocr_single_image_low_confidence_fallback_worse(self, mock_fallback):
        engine = MagicMock()
        engine.extract_text_with_confidence.return_value = ("good easyocr text", 20.0)

        mock_fallback.return_value = "bad"

        result = OCRService._ocr_single_image("img", engine)

        self.assertEqual(result, "good easyocr text")

    @patch("file_processing.services.ocr_service.TesseractEngine")
    def test_try_tesseract_fallback_generic_exception(self, mock_tesseract):
        mock_engine = MagicMock()
        mock_engine.extract_text_with_confidence.side_effect = Exception("boom")

        mock_tesseract.return_value = mock_engine

        result = OCRService._try_tesseract_fallback("img")

        self.assertEqual(result, "")


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

class TestUploadService(TestCase):
    def _post_file(self, name, content, content_type):
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/upload/", {"file": f}, format="multipart")
    
    def generate_valid_pdf_bytes(self):
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.drawString(100, 750, "Hello PDF")
        p.save()
        buffer.seek(0)
        return buffer.read()

    def generate_valid_xlsx_bytes(self):
        buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()

    def generate_valid_xls_bytes(self):
        import xlwt

        buffer = BytesIO()
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "Hello XLS")
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()
    
    def test_is_ole_container_returns_true_for_ole_signature(self):
        xls_content = self.generate_valid_xls_bytes()
        file_obj = SimpleUploadedFile(
            "legacy.xls",
            xls_content,
            content_type="application/vnd.ms-excel",
        )

        self.assertTrue(_is_ole_container(file_obj))
    
    def test_is_ole_container_returns_false_on_seek_error(self):
        class BrokenFile:
            def seek(self, *_args, **_kwargs):
                raise OSError("seek failed")

        self.assertFalse(_is_ole_container(BrokenFile()))

    def test_is_legacy_xls_content_returns_true_for_valid_xls(self):
        xls_content = self.generate_valid_xls_bytes()
        file_obj = SimpleUploadedFile(
            "legacy.xls",
            xls_content,
            content_type="application/vnd.ms-excel",
        )

        self.assertTrue(_is_legacy_xls_content(file_obj))

    def test_is_legacy_xls_content_returns_false_for_non_xls_payload(self):
        file_obj = SimpleUploadedFile(
            "fake.xlsx",
            b"not an xls payload",
            content_type="application/octet-stream",
        )

        self.assertFalse(_is_legacy_xls_content(file_obj))

    def test_is_legacy_xls_content_returns_false_when_xlrd_unavailable(self):
        file_obj = SimpleUploadedFile(
            "legacy.xls",
            self.generate_valid_xls_bytes(),
            content_type="application/vnd.ms-excel",
        )
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "xlrd":
                raise ImportError("xlrd unavailable")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            self.assertFalse(_is_legacy_xls_content(file_obj))

    def test_has_zip_signature_returns_false_on_seek_error(self):
        class BrokenFile:
            def seek(self, *_args, **_kwargs):
                raise OSError("seek failed")

        self.assertFalse(_has_zip_signature(BrokenFile()))

    def test_validate_pdf_reader_creation_fails(self):
        with patch("file_processing.services.upload_service.PdfReader") as mock_reader:
            mock_reader.side_effect = Exception("parse error")

            f = SimpleUploadedFile(
                "doc.pdf",
                b"%PDF-test",
                content_type="application/pdf",
            )
            is_valid, error = validate_pdf(f)
            self.assertFalse(is_valid)
            self.assertIn("corrupt", error.lower())

    def test_validate_pdf_structure_pdf_read_error(self):
        with patch("file_processing.services.upload_service.PdfReader") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.is_encrypted = False
            type(mock_instance).pages = PropertyMock(
                side_effect=PdfReadError("bad xref")
            )
            mock_cls.return_value = mock_instance

            f = SimpleUploadedFile(
                "doc.pdf",
                b"%PDF-test",
                content_type="application/pdf",
            )
            is_valid, error = validate_pdf(f)
            self.assertFalse(is_valid)
            self.assertIn("corrupt", error.lower())

    def test_validate_pdf_structure_generic_exception(self):
        with patch("file_processing.services.upload_service.PdfReader") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.is_encrypted = False
            type(mock_instance).pages = PropertyMock(
                side_effect=Exception("unexpected")
            )
            mock_cls.return_value = mock_instance

            f = SimpleUploadedFile(
                "doc.pdf",
                b"%PDF-test",
                content_type="application/pdf",
            )
            is_valid, error = validate_pdf(f)
            self.assertFalse(is_valid)
            self.assertIn("corrupt", error.lower())

    @patch("file_processing.services.upload_service.validate_mime_type")
    def test_process_upload_mime_validation_failure(self, mock_validate):
        from file_processing.services.upload_service import process_upload

        mock_validate.return_value = (False, "Invalid MIME")

        f = SimpleUploadedFile(
            "file.pdf",
            b"%PDF-1.4",
            content_type="application/pdf",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "Invalid MIME")

    @patch("file_processing.services.upload_service.process_uploaded_excel")
    def test_process_upload_excel_failure(self, mock_excel):
        mock_excel.return_value = (False, "Excel error", None)

        xlsx_content = self.generate_valid_xlsx_bytes()

        resp = self._post_file(
            "sheet.xlsx",
            xlsx_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")

    @patch("file_processing.services.upload_service.validate_file")
    @patch("file_processing.services.upload_service.process_uploaded_excel")
    @patch("file_processing.services.upload_service.save_temp_file")
    def test_process_upload_processing_exception(self, mock_save, mock_excel, mock_validate):
        from file_processing.services.upload_service import process_upload

        mock_validate.return_value = (True, None)
        mock_save.return_value = "/tmp/test.xlsx"
        mock_excel.side_effect = Exception("disk failure")

        f = SimpleUploadedFile(
            "file.xlsx",
            b"dummy",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with self.assertRaises(Exception):
            process_upload(f)

    @patch("file_processing.services.upload_service.OCRService.process_pdf")
    @patch("file_processing.services.upload_service.NonOCRPDFService.extract_non_ocr_pdf_to_json")
    def test_process_pdf_ocr_fallback_called(self, mock_non_ocr, mock_ocr):
        from file_processing.services.upload_service import _process_pdf

        mock_non_ocr.return_value = None
        mock_ocr.return_value = {"text": "ocr"}

        pdf_doc = self.generate_valid_pdf_bytes()

        f = SimpleUploadedFile(
            "doc.pdf",
            pdf_doc,
            content_type="application/pdf",
        )

        success, error, data = _process_pdf("/tmp/file.pdf", f)

        self.assertTrue(success)
        mock_ocr.assert_called_once()

    @patch("file_processing.services.upload_service.OCRService.process_pdf")
    @patch("file_processing.services.upload_service.NonOCRPDFService.extract_non_ocr_pdf_to_json")
    def test_process_pdf_non_ocr_exception_triggers_ocr(self, mock_non_ocr, mock_ocr):
        from file_processing.services.upload_service import _process_pdf

        mock_non_ocr.side_effect = Exception("Non-OCR crash")
        mock_ocr.return_value = {"content": "ocr"}

        pdf_doc = self.generate_valid_pdf_bytes()

        f = SimpleUploadedFile(
            "doc.pdf",
            pdf_doc,
            content_type="application/pdf",
        )

        success, error, data = _process_pdf("/tmp/file.pdf", f)

        self.assertTrue(success)
        mock_ocr.assert_called_once()

    def test_process_upload_service_unsupported_extension(self):
        from file_processing.services.upload_service import process_upload

        f = SimpleUploadedFile(
            "file.xyz",
            b"data",
            content_type="application/octet-stream",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertIn("Unsupported file type", error)

    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_validate_file_failure(self, mock_validate):
        from file_processing.services.upload_service import process_upload

        mock_validate.return_value = (False, "Invalid file")

        f = SimpleUploadedFile(
            "doc.pdf",
            b"%PDF-1.4",
            content_type="application/pdf",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "Invalid file")

    @patch("file_processing.services.upload_service._process_pdf")
    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service.validate_mime_type")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_pdf_processing_failure(
        self, mock_validate_file, mock_mime, mock_save, mock_pdf
    ):
        from file_processing.services.upload_service import process_upload

        mock_validate_file.return_value = (True, None)
        mock_mime.return_value = (True, None)
        mock_save.return_value = "/tmp/test.pdf"
        mock_pdf.return_value = (False, "PDF error", None)

        f = SimpleUploadedFile(
            "doc.pdf",
            b"%PDF-1.4",
            content_type="application/pdf",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "PDF error")

    @patch("file_processing.services.upload_service.validate_file")
    @patch("file_processing.services.upload_service.validate_mime_type")
    @patch("file_processing.services.upload_service.save_temp_file")
    def test_process_upload_else_branch_unsupported_extension(
        self, mock_save, mock_mime, mock_validate
    ):
        from file_processing.services.upload_service import process_upload

        mock_validate.return_value = (True, None)
        mock_mime.return_value = (True, None)
        mock_save.return_value = "/tmp/test.doc"

        f = SimpleUploadedFile(
            "file.doc",
            b"dummy",
            content_type="application/msword",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "Unsupported file type")

    def test_get_empty_page_numbers_invalid_data(self):
        self.assertEqual(_get_empty_page_numbers(None), [])
        self.assertEqual(_get_empty_page_numbers({}), [])
        self.assertEqual(_get_empty_page_numbers({"other_key": "val"}), [])
