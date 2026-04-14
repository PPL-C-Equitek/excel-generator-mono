from unittest.mock import Mock

from django.http import HttpResponse
from django.test import SimpleTestCase
from rest_framework import status

from api.handlers import (
    BaseDirectDownloadHandler,
    BaseExportHandler,
    CsvDirectDownloadHandler,
    ExcelDirectDownloadHandler,
    HistoryDownloadHandler,
)


class DirectDownloadHandlerTest(SimpleTestCase):
    def test_base_direct_download_builds_attachment_response(self):
        strategy = Mock()
        strategy.export_storage_dir.return_value = "/tmp/exports"
        open_file = Mock(return_value=b"file-handle")
        resolve_download_filename = Mock(return_value="custom.csv")
        handler = BaseDirectDownloadHandler(
            strategy=strategy,
            resolve_download_filename=resolve_download_filename,
            open_file=open_file,
        )

        response = handler.build_response(
            artifact={"file_name": "export.csv", "artifact_type": "csv", "content_type": "text/csv"},
            requested_name="my.csv",
        )

        open_file.assert_called_once_with("/tmp/exports/export.csv", "rb")
        resolve_download_filename.assert_called_once_with(
            requested_name="my.csv",
            default_name="export.csv",
            artifact_type="csv",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_csv_direct_download_passes_file_id(self):
        strategy = Mock()
        strategy.export_storage_dir.return_value = "/tmp/csv"
        resolver = Mock(return_value={"ok": True})
        handler = CsvDirectDownloadHandler(
            strategy=strategy,
            resolve_download_filename=Mock(),
            open_file=Mock(),
            resolver=resolver,
        )

        result = handler.resolve_artifact("csv_token")

        self.assertEqual(result, {"ok": True})
        resolver.assert_called_once_with(file_id="csv_token", storage_dir="/tmp/csv")

    def test_excel_direct_download_passes_export_id(self):
        strategy = Mock()
        strategy.export_storage_dir.return_value = "/tmp/excel"
        resolver = Mock(return_value={"ok": True})
        handler = ExcelDirectDownloadHandler(
            strategy=strategy,
            resolve_download_filename=Mock(),
            open_file=Mock(),
            resolver=resolver,
        )

        result = handler.resolve_artifact("xlsx_token")

        self.assertEqual(result, {"ok": True})
        resolver.assert_called_once_with(export_id="xlsx_token", storage_dir="/tmp/excel")


class DummyRequestSerializer:
    def __init__(self, data):
        self.data = data
        self.validated_data = {"output_json": {"ok": True}}

    def is_valid(self):
        return True


class DummyInvalidRequestSerializer:
    def __init__(self, data):
        self.data = data
        self.errors = {"output_json": ["required"]}

    def is_valid(self):
        return False


class BaseExportHandlerTest(SimpleTestCase):
    def test_handle_returns_400_for_invalid_request_serializer(self):
        request = Mock()
        request.data = {}

        handler = BaseExportHandler(
            strategy=Mock(),
            build_error_response=Mock(),
            build_success_response=Mock(),
        )
        handler.request_serializer_class = DummyInvalidRequestSerializer

        response = handler.handle(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"output_json": ["required"]})

    def test_handle_returns_success_response_when_strategy_succeeds(self):
        request = Mock()
        request.data = {"output_json": {"ok": True}}
        strategy = Mock(return_value={"file_id": "csv_token"})
        strategy.export_to_filesystem = Mock(return_value={"file_id": "csv_token"})
        success_response = HttpResponse(status=200)
        build_success_response = Mock(return_value=success_response)

        handler = BaseExportHandler(
            strategy=strategy,
            build_error_response=Mock(),
            build_success_response=build_success_response,
        )
        handler.request_serializer_class = DummyRequestSerializer
        handler.response_serializer_class = object
        handler.invalid_metadata_message = "invalid metadata"

        response = handler.handle(request)

        self.assertIs(response, success_response)
        strategy.export_to_filesystem.assert_called_once_with({"ok": True})
        build_success_response.assert_called_once_with(
            metadata={"file_id": "csv_token"},
            response_serializer_class=object,
            invalid_metadata_message="invalid metadata",
        )

    def test_handle_delegates_error_response_when_strategy_raises(self):
        request = Mock()
        request.data = {"output_json": {"ok": True}}
        error = ValueError("boom")
        strategy = Mock()
        strategy.export_to_filesystem = Mock(side_effect=error)
        error_response = HttpResponse(status=500)
        build_error_response = Mock(return_value=error_response)

        handler = BaseExportHandler(
            strategy=strategy,
            build_error_response=build_error_response,
            build_success_response=Mock(),
        )
        handler.request_serializer_class = DummyRequestSerializer
        handler.validation_error_types = (TypeError,)
        handler.generation_error_types = (RuntimeError,)
        handler.invalid_request_message = "invalid request"
        handler.internal_error_message = "internal error"
        handler.validation_log_message = "validation log"
        handler.generation_log_message = "generation log"
        handler.unexpected_log_message = "unexpected log"

        response = handler.handle(request)

        self.assertIs(response, error_response)
        build_error_response.assert_called_once_with(
            error=error,
            validation_error_types=(TypeError,),
            generation_error_types=(RuntimeError,),
            invalid_request_message="invalid request",
            internal_error_message="internal error",
            validation_log_message="validation log",
            generation_log_message="generation log",
            unexpected_log_message="unexpected log",
        )


class HistoryDownloadHandlerTest(SimpleTestCase):
    def test_handle_returns_response_for_fresh_artifact(self):
        resolve_history_download_artifact = Mock(
            return_value=("export.csv", "csv", "/tmp/export.csv", False)
        )
        open_file = Mock(return_value=b"file-handle")
        resolve_download_filename = Mock(return_value="result.csv")
        get_history_download_content_type = Mock(return_value="text/csv")
        handler = HistoryDownloadHandler(
            resolve_history_download_artifact=resolve_history_download_artifact,
            regenerate_history_download_artifact_after_stale_cache=Mock(),
            resolve_download_filename=resolve_download_filename,
            get_history_download_content_type=get_history_download_content_type,
            history_download_internal_error_response=Mock(),
            invalid_stored_output_error_types=(TypeError,),
            generation_error_types=(ValueError,),
            open_file=open_file,
            logger=Mock(),
        )

        response = handler.handle(
            history=Mock(),
            owner=Mock(),
            file_format="csv",
            requested_name="anything.csv",
        )

        open_file.assert_called_once_with("/tmp/export.csv", "rb")
        resolve_download_filename.assert_called_once_with(
            requested_name="anything.csv",
            default_name="export.csv",
            artifact_type="csv",
        )
        get_history_download_content_type.assert_called_once_with("csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
