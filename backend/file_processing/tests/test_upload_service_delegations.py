from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from file_processing.services import upload_service


class TestUploadServiceDelegations(TestCase):
    def test_validate_file_content_delegates_to_file_validation_service(self):
        uploaded = SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf")

        with patch(
            "file_processing.services.upload_service.file_validation_service._validate_file_content",
            return_value="sentinel",
        ) as mock_delegate:
            result = upload_service._validate_file_content(uploaded, ".pdf")

        self.assertEqual(result, "sentinel")
        mock_delegate.assert_called_once()

    def test_check_pdf_structure_delegates_to_pdf_validation_service(self):
        reader = object()
        with patch(
            "file_processing.services.upload_service.pdf_validation_service.check_pdf_structure",
            return_value=(True, 10),
        ) as mock_delegate:
            result = upload_service.check_pdf_structure(reader)

        self.assertEqual(result, (True, 10))
        mock_delegate.assert_called_once_with(reader)

    def test_validate_xlsx_mime_structure_delegates(self):
        uploaded = SimpleUploadedFile("a.xlsx", b"PK\x03\x04", content_type="application/zip")

        with patch(
            "file_processing.services.upload_service.mime_validation_service._validate_xlsx_mime_structure",
            return_value=("valid", None),
        ) as mock_delegate:
            result = upload_service._validate_xlsx_mime_structure(uploaded)

        self.assertEqual(result, ("valid", None))
        mock_delegate.assert_called_once()

    def test_validate_word_mime_structure_delegates(self):
        uploaded = SimpleUploadedFile("a.docx", b"PK\x03\x04", content_type="application/zip")

        with patch(
            "file_processing.services.upload_service.mime_validation_service._validate_word_mime_structure",
            return_value=None,
        ) as mock_delegate:
            result = upload_service._validate_word_mime_structure(uploaded, ".docx")

        self.assertIsNone(result)
        mock_delegate.assert_called_once()

    def test_resolve_txt_detected_mime_delegates(self):
        uploaded = SimpleUploadedFile("a.txt", b"abc", content_type="text/plain")

        with patch(
            "file_processing.services.upload_service.mime_validation_service._resolve_txt_detected_mime",
            return_value="text/plain",
        ) as mock_delegate:
            result = upload_service._resolve_txt_detected_mime(uploaded, "application/octet-stream")

        self.assertEqual(result, "text/plain")
        mock_delegate.assert_called_once_with(uploaded, "application/octet-stream")

    def test_read_head_delegates(self):
        uploaded = SimpleUploadedFile("a.txt", b"abc", content_type="text/plain")

        with patch(
            "file_processing.services.upload_service.mime_validation_service._read_head",
            return_value=b"abc",
        ) as mock_delegate:
            result = upload_service._read_head(uploaded, 3)

        self.assertEqual(result, b"abc")
        mock_delegate.assert_called_once_with(uploaded, 3)

    def test_detect_mime_delegates(self):
        with patch(
            "file_processing.services.upload_service.mime_validation_service._detect_mime",
            return_value="text/plain",
        ) as mock_delegate:
            result = upload_service._detect_mime(b"abc", ".txt")

        self.assertEqual(result, "text/plain")
        self.assertTrue(mock_delegate.called)

    def test_validate_txt_content_delegates(self):
        uploaded = SimpleUploadedFile("a.txt", b"abc", content_type="text/plain")

        with patch(
            "file_processing.services.upload_service.mime_validation_service._validate_txt_content",
            return_value=(True, None),
        ) as mock_delegate:
            result = upload_service._validate_txt_content(uploaded, "text/plain")

        self.assertEqual(result, (True, None))
        mock_delegate.assert_called_once()
