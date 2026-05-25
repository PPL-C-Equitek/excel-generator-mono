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

    def test_base_upload_processing_strategy_abstract_process_raises_negative(self):
        from file_processing.services.upload_service import UploadProcessingStrategy

        class StubStrategy(UploadProcessingStrategy):
            def process(self, file_path, uploaded_file):
                return super().process(file_path, uploaded_file)

        with self.assertRaises(NotImplementedError):
            StubStrategy().process("/tmp/file.any", object())

    @patch("file_processing.services.upload_service._process_pdf")
    def test_pdf_upload_strategy_wraps_pdf_processor_positive(self, mock_process_pdf):
        from file_processing.services.upload_service import PdfUploadStrategy

        uploaded_file = object()
        mock_process_pdf.return_value = (True, None, {"content": []})

        result = PdfUploadStrategy().process("/tmp/file.pdf", uploaded_file)

        self.assertEqual(result, (True, None, {"content": []}))
        mock_process_pdf.assert_called_once_with("/tmp/file.pdf", uploaded_file)

    @patch("file_processing.services.upload_service.process_uploaded_excel")
    def test_excel_upload_strategy_wraps_excel_processor_positive(self, mock_process_uploaded_excel):
        from file_processing.services.upload_service import ExcelUploadStrategy

        mock_process_uploaded_excel.return_value = (True, None, {"rows": []})

        result = ExcelUploadStrategy().process("/tmp/file.xlsx", object())

        self.assertEqual(result, (True, None, {"rows": []}))
        mock_process_uploaded_excel.assert_called_once_with("/tmp/file.xlsx")

    @patch("file_processing.services.upload_service.process_uploaded_csv")
    def test_csv_upload_strategy_wraps_csv_processor_positive(self, mock_process_uploaded_csv):
        from file_processing.services.upload_service import CsvUploadStrategy

        mock_process_uploaded_csv.return_value = (True, None, {"rows": []})

        result = CsvUploadStrategy().process("/tmp/file.csv", object())

        self.assertEqual(result, (True, None, {"rows": []}))
        mock_process_uploaded_csv.assert_called_once_with("/tmp/file.csv")

    @patch("file_processing.services.upload_service.process_uploaded_txt")
    def test_txt_upload_strategy_wraps_txt_processor_positive(self, mock_process_uploaded_txt):
        from file_processing.services.upload_service import TxtUploadStrategy

        mock_process_uploaded_txt.return_value = (True, None, {"text": "ok"})

        result = TxtUploadStrategy().process("/tmp/file.txt", object())

        self.assertEqual(result, (True, None, {"text": "ok"}))
        mock_process_uploaded_txt.assert_called_once_with("/tmp/file.txt")

    @patch("file_processing.services.upload_service.process_word")
    def test_word_upload_strategy_wraps_word_processor_with_extension_positive(self, mock_process_word):
        from file_processing.services.upload_service import WordUploadStrategy

        mock_process_word.return_value = (True, None, {"content": []})

        result = WordUploadStrategy(".docx").process("/tmp/file.docx", object())

        self.assertEqual(result, (True, None, {"content": []}))
        mock_process_word.assert_called_once_with("/tmp/file.docx", ".docx")

    @patch("file_processing.services.upload_service._process_image")
    def test_image_upload_strategy_wraps_image_processor_positive(self, mock_process_image):
        from file_processing.services.upload_service import ImageUploadStrategy

        mock_process_image.return_value = (True, None, {"content": []})

        result = ImageUploadStrategy().process("/tmp/file.png", object())

        self.assertEqual(result, (True, None, {"content": []}))
        mock_process_image.assert_called_once_with("/tmp/file.png")

    def test_get_upload_processing_strategy_rejects_unsupported_extension_negative(self):
        from file_processing.services.upload_service import get_upload_processing_strategy

        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            get_upload_processing_strategy(".exe")


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

    def test_dispatch_upload_processing_returns_unsupported_tuple_negative(self):
        result = _dispatch_upload_processing(".exe", "/tmp/file.exe", object())

        self.assertEqual(result, (False, "Unsupported file type", None))


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


class ProcessUploadStrategyHelperContractTest(SimpleTestCase):
    def test_upload_service_exposes_process_upload_with_strategy_helper(self):
        from file_processing.services import upload_service

        self.assertTrue(hasattr(upload_service, "_process_upload_with_strategy"))

    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service._process_upload_with_strategy")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_delegates_to_strategy_helper_positive(
        self,
        mock_validate_file,
        mock_process_upload_with_strategy,
        mock_save_temp_file,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "report.PDF"
        mock_validate_file.return_value = (True, None)
        mock_save_temp_file.return_value = "/tmp/report.pdf"
        mock_process_upload_with_strategy.return_value = (True, None, {"content": []})

        result = process_upload(uploaded_file)

        self.assertEqual(result, (True, None, None, {"content": []}))
        mock_process_upload_with_strategy.assert_called_once_with(
            ".pdf",
            "/tmp/report.pdf",
            uploaded_file,
        )

    @patch("file_processing.services.upload_service.save_temp_file")
    @patch("file_processing.services.upload_service._process_upload_with_strategy")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_reraises_strategy_helper_error_negative(
        self,
        mock_validate_file,
        mock_process_upload_with_strategy,
        mock_save_temp_file,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "report.csv"
        mock_validate_file.return_value = (True, None)
        mock_save_temp_file.return_value = "/tmp/report.csv"
        mock_process_upload_with_strategy.side_effect = RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "boom"):
            process_upload(uploaded_file)

    @patch("file_processing.services.upload_service._process_upload_with_strategy")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_short_circuits_before_strategy_helper_edge(
        self,
        mock_validate_file,
        mock_process_upload_with_strategy,
    ):
        uploaded_file = MagicMock()
        uploaded_file.name = "bad.exe"
        mock_validate_file.return_value = (False, "Unsupported file type")

        result = process_upload(uploaded_file)

        self.assertEqual(result, (False, "Unsupported file type", None, None))
        mock_process_upload_with_strategy.assert_not_called()
