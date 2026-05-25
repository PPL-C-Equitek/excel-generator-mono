from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from file_processing.services.upload_service import _dispatch_upload_processing, process_upload


class UploadProcessingStrategyContractTest(SimpleTestCase):
    def test_upload_service_exposes_strategy_types_and_registry(self):
        from file_processing.services import upload_service

        self.assertTrue(hasattr(upload_service, "UploadProcessingStrategy"))
        self.assertTrue(hasattr(upload_service, "PdfUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "ExcelUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "CsvUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "TxtUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "WordUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "ImageUploadStrategy"))
        self.assertTrue(hasattr(upload_service, "get_upload_processing_strategy"))


class DispatchUploadProcessingDelegationContractTest(SimpleTestCase):
    @patch("file_processing.services.upload_service.get_upload_processing_strategy")
    def test_dispatch_upload_processing_delegates_to_strategy_positive(
        self,
        mock_get_strategy,
    ):
        uploaded_file = object()
        strategy = MagicMock()
        strategy.process.return_value = (True, None, {"content": []})
        mock_get_strategy.return_value = strategy

        result = _dispatch_upload_processing(".pdf", "/tmp/file.pdf", uploaded_file)

        self.assertEqual(result, (True, None, {"content": []}))
        mock_get_strategy.assert_called_once_with(".pdf")
        strategy.process.assert_called_once_with("/tmp/file.pdf", uploaded_file)

    @patch("file_processing.services.upload_service.get_upload_processing_strategy")
    def test_dispatch_upload_processing_propagates_strategy_failure_negative(
        self,
        mock_get_strategy,
    ):
        strategy = MagicMock()
        strategy.process.side_effect = RuntimeError("boom")
        mock_get_strategy.return_value = strategy

        with self.assertRaisesRegex(RuntimeError, "boom"):
            _dispatch_upload_processing(".csv", "/tmp/file.csv", object())

    @patch("file_processing.services.upload_service.get_upload_processing_strategy")
    def test_dispatch_upload_processing_passes_extension_alias_edge(
        self,
        mock_get_strategy,
    ):
        strategy = MagicMock()
        strategy.process.return_value = (False, "unsupported", None)
        mock_get_strategy.return_value = strategy

        _dispatch_upload_processing(".xlsx", "/tmp/file.xlsx", object())

        mock_get_strategy.assert_called_once_with(".xlsx")


class ProcessUploadStrategyDelegationContractTest(SimpleTestCase):
    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service._dispatch_upload_processing")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_delegates_normalized_extension_positive(
        self,
        mock_validate_file,
        mock_dispatch,
        mock_save_temp_file,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "Report.XLSX"
        mock_validate_file.return_value = (True, None)
        mock_save_temp_file.return_value = "/tmp/report.xlsx"
        mock_dispatch.return_value = (True, None, {"content": []})

        result = process_upload(uploaded_file)

        self.assertEqual(result, (True, None, None, {"content": []}))
        mock_dispatch.assert_called_once_with(".xlsx", "/tmp/report.xlsx", uploaded_file)

    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service._dispatch_upload_processing")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_propagates_dispatch_error_negative(
        self,
        mock_validate_file,
        mock_dispatch,
        mock_save_temp_file,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "report.csv"
        mock_validate_file.return_value = (True, None)
        mock_save_temp_file.return_value = "/tmp/report.csv"
        mock_dispatch.return_value = (False, "broken", None)

        result = process_upload(uploaded_file)

        self.assertEqual(result, (False, "broken", None, None))

    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service._dispatch_upload_processing")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_normalizes_jpeg_extension_edge(
        self,
        mock_validate_file,
        mock_dispatch,
        mock_save_temp_file,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "scan.JPEG"
        mock_validate_file.return_value = (True, None)
        mock_save_temp_file.return_value = "/tmp/scan.jpeg"
        mock_dispatch.return_value = (True, None, {"content": []})

        process_upload(uploaded_file)

        mock_dispatch.assert_called_once_with(".jpeg", "/tmp/scan.jpeg", uploaded_file)
