import zipfile
from io import BytesIO
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from file_processing.services.export_service import (
    OutputCSVGenerationError,
    OutputLLMValidationError,
)
from file_processing.services import word_validation_service


class ExportCsvEndpointTest(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

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
                        {"item_name": "Pena", "quantity": 5, "price": 10000},
                    ],
                }
            ],
        }

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_returns_200_and_metadata_for_valid_payload(
        self,
        mock_export_csv_to_filesystem,
    ):
        output_json = self._valid_output_json()
        saved_metadata = {
            "file_id": "csv_8fa2e3d1",
            "file_name": "export_123.csv",
            "artifact_type": "csv",
            "size_bytes": 15,
            "created_at": "2026-03-06T10:00:00Z",
        }

        mock_export_csv_to_filesystem.return_value = saved_metadata

        response = self.client.post(
            "/export/csv",
            {"output_json": output_json},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_id"], "csv_8fa2e3d1")
        self.assertEqual(response.data["file_name"], "export_123.csv")
        self.assertEqual(response.data["artifact_type"], "csv")
        self.assertEqual(response.data["size_bytes"], 15)
        self.assertNotIn("path", response.data)
        self.assertNotIn("file_path", response.data)

        mock_export_csv_to_filesystem.assert_called_once()

    def test_export_csv_rejects_missing_output_json(self):
        response = self.client.post("/export/csv", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("output_json", response.data)

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_rejects_invalid_schema_payload(
        self,
        mock_export_csv_to_filesystem,
    ):
        mock_export_csv_to_filesystem.side_effect = OutputLLMValidationError(
            "Invalid output schema."
        )

        response = self.client.post(
            "/export/csv",
            {"output_json": self._valid_output_json()},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue("detail" in response.data or "message" in response.data)

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_returns_500_when_filesystem_save_fails(
        self,
        mock_export_csv_to_filesystem,
    ):
        mock_export_csv_to_filesystem.side_effect = OutputCSVGenerationError(
            "Disk write failed"
        )

        response = self.client.post(
            "/export/csv",
            {"output_json": self._valid_output_json()},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertTrue("detail" in response.data or "message" in response.data)

    def test_export_csv_rejects_get(self):
        response = self.client.get("/export/csv")
        self.assertEqual(response.status_code, 405)


class TestWordValidationServiceCoverage(TestCase):
    class _DummyFile:
        def seek(self, *_args, **_kwargs):
            return 0

        def read(self, *_args, **_kwargs):
            return b""

    class _BrokenFile:
        def seek(self, *_args, **_kwargs):
            raise OSError("seek failed")

        def read(self, *_args, **_kwargs):
            raise OSError("read failed")

    class _NoNextHandler(word_validation_service.WordValidationHandler):
        def handle(self, context):
            return self._next(context)

    def test_base_handler_next_without_next_returns_success(self):
        handler = self._NoNextHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=self._DummyFile(),
            ext=".docx",
        )

        self.assertEqual(handler.handle(context), (True, None))

    def test_base_handler_handle_raises_not_implemented(self):
        handler = word_validation_service.WordValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=self._DummyFile(),
            ext=".docx",
        )

        with self.assertRaises(NotImplementedError):
            handler.handle(context)

    @patch("file_processing.services.word_validation_service.zipfile.ZipFile", side_effect=Exception("bad zip"))
    def test_docx_structure_handler_returns_corrupt_on_exception(self, _mock_zip):
        handler = word_validation_service.DocxStructureValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=SimpleUploadedFile("bad.docx", b"broken"),
            ext=".docx",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=False)
    def test_doc_encrypted_handler_rejects_non_ole(self, _mock_is_ole):
        handler = word_validation_service.DocEncryptedValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=SimpleUploadedFile("not-ole.doc", b"plain"),
            ext=".doc",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=True)
    def test_doc_encrypted_handler_returns_corrupt_on_stream_exception(self, _mock_is_ole):
        handler = word_validation_service.DocEncryptedValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=self._BrokenFile(),
            ext=".doc",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=False)
    def test_doc_structure_handler_rejects_non_ole(self, _mock_is_ole):
        handler = word_validation_service.DocStructureValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=SimpleUploadedFile("bad.doc", b"plain"),
            ext=".doc",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=True)
    def test_doc_structure_handler_rejects_missing_worddocument(self, _mock_is_ole):
        handler = word_validation_service.DocStructureValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=SimpleUploadedFile("bad.doc", b"ole-but-missing-stream"),
            ext=".doc",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=True)
    def test_doc_structure_handler_returns_corrupt_on_exception(self, _mock_is_ole):
        handler = word_validation_service.DocStructureValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=self._BrokenFile(),
            ext=".doc",
        )

        self.assertEqual(
            handler.handle(context),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    def test_word_page_count_handler_rejects_when_over_limit(self):
        handler = word_validation_service.WordPageCountValidationHandler()
        context = word_validation_service.WordValidationContext(
            uploaded_file=self._DummyFile(),
            ext=".docx",
            page_count=word_validation_service.MAX_WORD_PAGES + 1,
        )

        is_valid, error = handler.handle(context)
        self.assertFalse(is_valid)
        self.assertIn("maximum allowed page count", error)

    def test_check_docx_encrypted_allows_non_ole(self):
        f = SimpleUploadedFile("valid.docx", b"PK-not-ole-header")
        self.assertEqual(word_validation_service.check_docx_encrypted(f), (True, None))

    def test_check_docx_structure_rejects_missing_required_entries(self):
        content = BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types></Types>")
        f = SimpleUploadedFile("broken.docx", content.getvalue())

        self.assertEqual(
            word_validation_service.check_docx_structure(f),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    def test_extract_docx_page_count_returns_zero_when_pages_tag_missing(self):
        content = BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("docProps/app.xml", "<Properties><Company>X</Company></Properties>")
        with zipfile.ZipFile(BytesIO(content.getvalue()), "r") as archive:
            self.assertEqual(word_validation_service.extract_docx_page_count(archive), 0)

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=False)
    def test_check_doc_encrypted_rejects_non_ole(self, _mock_is_ole):
        f = SimpleUploadedFile("file.doc", b"plain")
        self.assertEqual(
            word_validation_service.check_doc_encrypted(f),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=True)
    def test_check_doc_encrypted_accepts_ole_without_encryption_markers(self, _mock_is_ole):
        f = SimpleUploadedFile("file.doc", b"WordDocument-data")
        self.assertEqual(word_validation_service.check_doc_encrypted(f), (True, None))

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=False)
    def test_check_doc_structure_rejects_non_ole(self, _mock_is_ole):
        f = SimpleUploadedFile("file.doc", b"plain")
        self.assertEqual(
            word_validation_service.check_doc_structure(f),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    @patch("file_processing.services.word_validation_service.is_ole_container", return_value=True)
    def test_check_doc_structure_returns_corrupt_on_exception(self, _mock_is_ole):
        self.assertEqual(
            word_validation_service.check_doc_structure(self._BrokenFile()),
            (False, word_validation_service.WORD_CORRUPT_ERROR),
        )

    def test_check_word_page_count_covers_both_branches(self):
        self.assertEqual(
            word_validation_service.check_word_page_count(
                word_validation_service.MAX_WORD_PAGES + 1
            ),
            (
                False,
                f"Word exceeds the maximum allowed page count of {word_validation_service.MAX_WORD_PAGES}.",
            ),
        )
        self.assertEqual(
            word_validation_service.check_word_page_count(
                word_validation_service.MAX_WORD_PAGES
            ),
            (True, None),
        )

    def test_is_ole_container_returns_false_when_stream_errors(self):
        self.assertFalse(word_validation_service.is_ole_container(self._BrokenFile()))
