from unittest.mock import patch
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from file_processing.services.export_service import (
    OutputCSVGenerationError,
    OutputLLMValidationError,
)


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
