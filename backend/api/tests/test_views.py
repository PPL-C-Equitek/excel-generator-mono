from django.test import TestCase
from unittest.mock import patch

from rest_framework.test import APIClient, APISimpleTestCase

from api.models import GroupMember
from file_processing.services.export_service import (
    OutputCSVDownloadLookupError,
    OutputCSVGenerationError,
    OutputLLMValidationError,
)


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

        response = self.client.get("/export/csv/download/csv_abc123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
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

        response = self.client.get("/export/csv/download/csv_bad-token")
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

        response = self.client.get("/export/csv/download/csv_deadbeef")
        response_data = self._response_data(response)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response_data.get("status"), "error")
        self.assertEqual(response_data.get("message"), "CSV file not found.")

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

        response = self.client.get("/export/csv/download/csv_abc123")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            response.data["message"],
            "Failed to download CSV due to internal error.",
        )

    def test_download_csv_endpoint_rejects_post_method(self):
        response = self.client.post("/export/csv/download/csv_abc123")

        self.assertEqual(response.status_code, 405)
