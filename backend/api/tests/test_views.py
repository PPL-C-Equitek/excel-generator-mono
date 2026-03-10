from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock, PropertyMock

from io import BytesIO
from reportlab.pdfgen import canvas
from openpyxl import Workbook

from rest_framework.test import APIClient, APISimpleTestCase

from api.models import GroupMember
from api.views import _resolve_download_filename, _sanitize_download_filename
from file_processing.services.export_service import (
    OutputCSVDownloadLookupError,
    OutputCSVGenerationError,
    OutputLLMValidationError,
)
from file_processing.services.upload_service import validate_pdf


class BaseApiViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()


class HealthCheckViewTest(BaseApiViewTest):
    def test_health_endpoint_returns_200(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_returns_correct_data(self):
        response = self.client.get("/health/")
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["message"], "Backend is running!")

    def test_health_endpoint_rejects_post(self):
        response = self.client.post("/health/")
        self.assertEqual(response.status_code, 405)


class AboutViewTest(BaseApiViewTest):
    def test_about_endpoint_returns_200(self):
        response = self.client.get("/about/")
        self.assertEqual(response.status_code, 200)

    def test_about_endpoint_returns_correct_data(self):
        response = self.client.get("/about/")
        self.assertEqual(response.data["team"], "PPL C - Equitek")
        self.assertEqual(response.data["project"], "Excel Generator")

    def test_about_endpoint_rejects_post(self):
        response = self.client.post("/about/")
        self.assertEqual(response.status_code, 405)


class MembersViewTest(BaseApiViewTest):
    @classmethod
    def setUpTestData(cls):
        GroupMember.objects.create(npm="2306152260", name="Steven Setiawan")
        GroupMember.objects.create(npm="2306152172", name="Siti Shofi Nadhifa")

    def test_members_endpoint_returns_200(self):
        response = self.client.get("/members/")
        self.assertEqual(response.status_code, 200)

    def test_members_endpoint_returns_group_and_members(self):
        response = self.client.get("/members/")
        self.assertEqual(response.data["group"], "Kelompok 7")
        self.assertEqual(len(response.data["members"]), 2)
        self.assertEqual(response.data["members"][0]["npm"], "2306152172")
        self.assertEqual(response.data["members"][0]["name"], "Siti Shofi Nadhifa")

    def test_members_endpoint_rejects_post(self):
        response = self.client.post("/members/")
        self.assertEqual(response.status_code, 405)


class UploadEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()

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

    def generate_private_pdf_bytes(self, password="secret"):
        valid_pdf_bytes = self.generate_valid_pdf_bytes()

        input_buffer = BytesIO(valid_pdf_bytes)
        output_buffer = BytesIO()

        reader = PdfReader(input_buffer)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)
        writer.write(output_buffer)

        output_buffer.seek(0)
        return output_buffer.read()

    def generate_valid_xlsx_bytes(self):
        buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_upload_pdf_success(self):
        pdf_doc = self.generate_valid_pdf_bytes()
        resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")
        self.assertEqual(resp.data["filename"], "doc.pdf")

    @patch("api.views.process_upload")
    def test_upload_xls_success(self, mock_process):
        mock_process.return_value = (True, None, "/tmp/file.xls", None)

        resp = self._post_file(
            "sheet.xls",
            b"dummy",
            "application/vnd.ms-excel",
        )

        self.assertEqual(resp.status_code, 200)

    def test_upload_xlsx_success(self):
        xlsx_content = self.generate_valid_xlsx_bytes()

        resp = self._post_file(
            "sheet.xlsx",
            xlsx_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.assertEqual(resp.status_code, 200)

    def test_upload_unsupported_type(self):
        resp = self._post_file("note.txt", b"hello", "text/plain")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_no_file(self):
        resp = self.client.post("/upload/", {}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_response_does_not_expose_path(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("path", resp.data)

    def test_upload_internal_server_error(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        with patch("api.views.process_upload") as mock_process_upload:
            mock_process_upload.side_effect = Exception("Unexpected failure")

            resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")

            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.data["status"], "error")
            self.assertIn("message", resp.data)

    def test_invalid_file_path_detection(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        with patch(
            "file_processing.services.upload_service.os.path.abspath"
        ) as mock_abspath:

            def fake_abspath(path):
                if "doc.pdf" in path:
                    return "/evil/path/file.pdf"
                return "/safe/base"

            mock_abspath.side_effect = fake_abspath

            with self.assertRaises(ValueError):
                from file_processing.services.upload_service import save_temp_file

                f = SimpleUploadedFile(
                    "doc.pdf", pdf_doc, content_type="application/pdf"
                )
                save_temp_file(f)

    def test_save_temp_file_success(self):
        from file_processing.services.upload_service import save_temp_file

        pdf_doc = self.generate_valid_pdf_bytes()

        f = SimpleUploadedFile(
            "doc.pdf",
            pdf_doc,
            content_type="application/pdf",
        )

        path = save_temp_file(f)

        self.assertTrue(path.endswith(".pdf"))

    def test_upload_pdf_uppercase_extension(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "DOC.PDF",
            pdf_doc,
            "application/pdf",
        )

        self.assertEqual(resp.status_code, 200)

    def test_file_header_not_pdf_with_extension_pdf(self):
        resp = self._post_file("doc.pdf", b"data", "application/pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_file_is_corrupt_pdf(self):
        pdf_doc = self.generate_valid_pdf_bytes()
        corrupt_pdf = pdf_doc[:20]

        resp = self._post_file("corrupt.pdf", corrupt_pdf, "application/pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_too_large(self):
        big_content = b"a" * (11 * 1024 * 1024)
        resp = self._post_file("big.pdf", big_content, "application/pdf")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_exact_10mb_allowed(self):
        valid_pdf = self.generate_valid_pdf_bytes()
        remaining_size = (10 * 1024 * 1024) - len(valid_pdf)

        padding = b"\0" * remaining_size
        exact_content = valid_pdf + padding
        resp = self._post_file("exact.pdf", exact_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)

    def test_upload_file_less_than_10mb_allowed(self):
        valid_pdf = self.generate_valid_pdf_bytes()
        padding = b"\0" * (5 * 1024 * 1024)
        less_content = valid_pdf + padding
        resp = self._post_file("small.pdf", less_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)

    def test_file_is_private_pdf(self):
        private_pdf = self.generate_private_pdf_bytes(password="1234")

        resp = self._post_file("private.pdf", private_pdf, "application/pdf")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_xls_extension_but_invalid_mime(self):
        resp = self._post_file(
            "fake.xls",
            b"not an excel file",
            "application/vnd.ms-excel",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")

    def test_xlsx_extension_but_invalid_mime(self):
        resp = self._post_file(
            "fake.xlsx",
            b"this is not an excel file",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_mime_detection_exception(self):
        with patch(
            "file_processing.services.upload_service.magic.from_buffer"
        ) as mock_magic:
            mock_magic.side_effect = Exception("libmagic failure")

            resp = self._post_file(
                "sheet.xlsx",
                b"dummy content",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.data["status"], "error")
            self.assertEqual(resp.data["message"], "Unable to determine file type.")

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

    def test_upload_pdf_too_many_pages(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        with patch(
            "file_processing.services.upload_service.PdfReader"
        ) as mock_reader_cls:
            mock_instance = MagicMock()
            mock_instance.is_encrypted = False
            mock_instance.pages = [MagicMock()] * 101
            mock_reader_cls.return_value = mock_instance

            resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.data["status"], "error")
            self.assertIn("100", resp.data["message"])

    @patch("api.views.process_upload")
    def test_upload_returns_extracted_text(self, mock_process):
        mock_process.return_value = (
            True,
            None,
            "/tmp/file.pdf",
            {"content": [{"page": 1, "type": "text", "lines": ["hello"]}]},
        )

        resp = self.client.post(
            "/upload/",
            {
                "file": SimpleUploadedFile(
                    "doc.pdf", b"%PDF-1.4", content_type="application/pdf"
                )
            },
            format="multipart",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("extracted", resp.data)

    @patch("file_processing.services.upload_service.OCRService.process_pdf")
    def test_ocr_failure_is_logged_and_returns_success(self, mock_ocr):
        mock_ocr.side_effect = Exception("OCR crash")

        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "doc.pdf",
            pdf_doc,
            "application/pdf",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")

    @patch("file_processing.services.upload_service.os.remove")
    def test_cleanup_failure_logged(self, mock_remove):
        mock_remove.side_effect = Exception("delete failed")

        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "doc.pdf",
            pdf_doc,
            "application/pdf",
        )

        self.assertEqual(resp.status_code, 200)

    @patch("file_processing.services.upload_service.os.path.exists")
    def test_cleanup_when_temp_file_not_exists(self, mock_exists):
        mock_exists.return_value = False

        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "doc.pdf",
            pdf_doc,
            "application/pdf",
        )

        self.assertEqual(resp.status_code, 200)

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

    @patch("file_processing.services.upload_service.process_uploaded_excel")
    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service.validate_mime_type")
    def test_process_upload_processing_exception(
        self, mock_mime, mock_save, mock_excel
    ):
        from file_processing.services.upload_service import process_upload

        mock_mime.return_value = (True, None)
        mock_save.return_value = "/tmp/test.xlsx"
        mock_excel.side_effect = Exception("disk failure")

        f = SimpleUploadedFile(
            "file.xlsx",
            b"dummy",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        success, error, _, _ = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "File processing failed")

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


class ExportCSVViewTest(APISimpleTestCase):
    def _valid_output_json(self):
        return {
            "document_info": {
                "source_type": "Excel",
                "filename": "laporan_tahunan.xlsx",
            },
            "summary": {
                "grand_total": 1500000,
                "period": "2026",
            },
            "content_data": [
                {
                    "table_name": "Sheet1_Januari",
                    "headers": ["item_name", "quantity", "price"],
                    "rows": [
                        {"item_name": "Kertas", "quantity": 10, "price": 50000},
                    ],
                }
            ],
        }

    def test_export_csv_endpoint_rejects_get_method(self):
        response = self.client.get("/export/csv")
        self.assertEqual(response.status_code, 405)

    def test_export_csv_endpoint_returns_400_if_output_json_missing(self):
        response = self.client.post("/export/csv", data={}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("output_json", response.data)

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_endpoint_returns_200_with_metadata(self, mocked_export):
        mocked_export.return_value = {
            "file_id": "csv_abc123",
            "file_name": "export_abc123.csv",
            "artifact_type": "csv",
            "size_bytes": 128,
            "created_at": "2026-03-07T10:00:00Z",
        }
        payload = {"output_json": self._valid_output_json()}

        response = self.client.post("/export/csv", data=payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_id"], "csv_abc123")
        self.assertEqual(response.data["file_name"], "export_abc123.csv")
        mocked_export.assert_called_once()

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_endpoint_returns_400_when_service_validation_fails(
        self,
        mocked_export,
    ):
        mocked_export.side_effect = OutputLLMValidationError("invalid schema")
        payload = {"output_json": self._valid_output_json()}

        response = self.client.post("/export/csv", data=payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["message"], "Invalid CSV export request.")

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_endpoint_returns_500_on_internal_error(self, mocked_export):
        mocked_export.side_effect = RuntimeError("disk full")
        payload = {"output_json": self._valid_output_json()}

        response = self.client.post("/export/csv", data=payload, format="json")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("Failed to generate CSV", response.data["message"])

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_endpoint_returns_500_on_generation_error(self, mocked_export):
        mocked_export.side_effect = OutputCSVGenerationError("storage failure")
        payload = {"output_json": self._valid_output_json()}

        response = self.client.post("/export/csv", data=payload, format="json")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            response.data["message"],
            "Failed to generate CSV due to internal error.",
        )

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_endpoint_returns_500_when_response_metadata_invalid(
        self,
        mocked_export,
    ):
        mocked_export.return_value = {
            "file_id": "csv_abc123",
            "file_name": "../unsafe.csv",
            "artifact_type": "csv",
            "size_bytes": 128,
            "created_at": "2026-03-07T10:00:00Z",
        }
        payload = {"output_json": self._valid_output_json()}

        response = self.client.post("/export/csv", data=payload, format="json")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("invalid response metadata", response.data["message"])


class DownloadCSVViewTest(APISimpleTestCase):
    def _response_data(self, response):
        if hasattr(response, "data"):
            return response.data
        return {}

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", create=True)
    def test_download_csv_endpoint_returns_200_with_attachment_headers(
        self,
        mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "export_abc123.csv",
            "file_path": "/safe/storage/export_abc123.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }
        mocked_open.return_value.__enter__.return_value = b"name,age\r\nZufar,21\r\n"

        response = self.client.get("/export/csv/csv_abc123/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(
            'attachment; filename="export_abc123.csv"',
            response["Content-Disposition"],
        )

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", create=True)
    def test_download_csv_endpoint_uses_custom_filename_from_query(
        self,
        mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "export_abc123.csv",
            "file_path": "/safe/storage/export_abc123.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }
        mocked_open.return_value.__enter__.return_value = b"name,age\r\nZufar,21\r\n"

        response = self.client.get(
            "/export/csv/csv_abc123/download?filename=laporan_tahunan"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'attachment; filename="laporan_tahunan.csv"',
            response["Content-Disposition"],
        )

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", create=True)
    def test_download_csv_endpoint_falls_back_to_default_filename_when_query_is_unsafe(
        self,
        mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "export_abc123.csv",
            "file_path": "/safe/storage/export_abc123.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }
        mocked_open.return_value.__enter__.return_value = b"name,age\r\nZufar,21\r\n"

        response = self.client.get(
            "/export/csv/csv_abc123/download?filename=..%2Fevil.csv"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'attachment; filename="export_abc123.csv"',
            response["Content-Disposition"],
        )

    @patch("api.views.resolve_csv_download_artifact", create=True)
    def test_download_csv_endpoint_returns_404_for_invalid_file_id(
        self,
        mocked_resolver,
    ):
        mocked_resolver.side_effect = OutputCSVDownloadLookupError("invalid file id")

        response = self.client.get("/export/csv/csv_bad-token/download")
        response_data = self._response_data(response)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data.get("status"), "error")
        self.assertEqual(response_data.get("message"), "CSV file not found.")

    @patch("api.views.resolve_csv_download_artifact", create=True)
    def test_download_csv_endpoint_returns_404_for_missing_file(
        self,
        mocked_resolver,
    ):
        mocked_resolver.side_effect = OutputCSVDownloadLookupError("missing file")

        response = self.client.get("/export/csv/csv_deadbeef/download")
        response_data = self._response_data(response)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data.get("status"), "error")
        self.assertEqual(response_data.get("message"), "CSV file not found.")

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", create=True)
    def test_download_csv_endpoint_returns_404_for_unsafe_artifact_filename(
        self,
        mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "../evil.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }

        response = self.client.get("/export/csv/csv_abc123/download")
        response_data = self._response_data(response)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data.get("status"), "error")
        self.assertEqual(response_data.get("message"), "CSV file not found.")
        mocked_open.assert_not_called()

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", side_effect=OSError("disk read failed"), create=True)
    def test_download_csv_endpoint_returns_500_when_reading_file_fails(
        self,
        _mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "export_abc123.csv",
            "file_path": "/safe/storage/export_abc123.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }

        response = self.client.get("/export/csv/csv_abc123/download")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            response.data["message"],
            "Failed to download CSV due to internal error.",
        )

    @patch("api.views.resolve_csv_download_artifact", create=True)
    @patch("api.views.open", side_effect=RuntimeError("unexpected read failure"), create=True)
    def test_download_csv_endpoint_returns_500_for_unexpected_error_when_opening_file(
        self,
        _mocked_open,
        mocked_resolver,
    ):
        mocked_resolver.return_value = {
            "file_name": "export_abc123.csv",
            "file_path": "/safe/storage/export_abc123.csv",
            "artifact_type": "csv",
            "content_type": "text/csv",
        }

        response = self.client.get("/export/csv/csv_abc123/download")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            response.data["message"],
            "Failed to download CSV due to internal error.",
        )

    def test_download_csv_endpoint_rejects_post_method(self):
        response = self.client.post("/export/csv/csv_abc123/download")

        self.assertEqual(response.status_code, 405)


class DownloadFilenameHelperTest(APISimpleTestCase):
    def test_sanitize_download_filename_rejects_empty_after_trim(self):
        self.assertIsNone(_sanitize_download_filename("   \r\n   "))

    def test_sanitize_download_filename_rejects_null_byte(self):
        self.assertIsNone(_sanitize_download_filename("report\x00.csv"))

    def test_sanitize_download_filename_rejects_dot_and_dotdot(self):
        self.assertIsNone(_sanitize_download_filename("."))
        self.assertIsNone(_sanitize_download_filename(".."))

    def test_resolve_download_filename_rewrites_wrong_extension(self):
        resolved = _resolve_download_filename(
            requested_name="laporan.txt",
            default_name="export_abc123.csv",
            artifact_type="csv",
        )
        self.assertEqual(resolved, "laporan.csv")

    def test_resolve_download_filename_keeps_matching_extension_case_insensitive(self):
        resolved = _resolve_download_filename(
            requested_name="laporan.CSV",
            default_name="export_abc123.csv",
            artifact_type="csv",
        )
        self.assertEqual(resolved, "laporan.CSV")
