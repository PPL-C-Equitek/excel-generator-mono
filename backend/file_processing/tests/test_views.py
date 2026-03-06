from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from file_processing.services.export_service import OutputLLMValidationError


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

    @patch("file_processing.views.save_export_artifact", create=True)
    @patch("file_processing.views.generate_csv_download_artifact", create=True)
    @patch("file_processing.views.map_output_csv", create=True)
    @patch("file_processing.views.validate_output_llm", create=True)
    def test_export_csv_returns_200_and_metadata_for_valid_payload(
        self,
        mock_validate_output_llm,
        mock_map_output_csv,
        mock_generate_csv_download_artifact,
        mock_save_export_artifact,
    ):
        output_json = self._valid_output_json()
        mapped_output = {"sheets": [{"name": "Sheet1", "headers": ["a"], "rows": [[1]]}]}
        artifact = {
            "type": "csv",
            "name": "Sheet1.csv",
            "content": b"header\r\nvalue\r\n",
        }
        saved_metadata = {
            "file_id": "csv_8fa2e3d1",
            "file_name": "export_123.csv",
            "artifact_type": "csv",
            "size_bytes": 15,
            "created_at": "2026-03-06T10:00:00Z",
        }

        mock_validate_output_llm.return_value = output_json
        mock_map_output_csv.return_value = mapped_output
        mock_generate_csv_download_artifact.return_value = artifact
        mock_save_export_artifact.return_value = saved_metadata

        response = self.client.post(
            "/api/export/csv",
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

        mock_validate_output_llm.assert_called_once_with(output_json)
        mock_map_output_csv.assert_called_once_with(output_json)
        mock_generate_csv_download_artifact.assert_called_once_with(mapped_output)
        mock_save_export_artifact.assert_called_once_with(artifact)

    def test_export_csv_rejects_missing_output_json(self):
        response = self.client.post("/api/export/csv", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("output_json", response.data)

    @patch("file_processing.views.validate_output_llm", create=True)
    def test_export_csv_rejects_invalid_schema_payload(self, mock_validate_output_llm):
        mock_validate_output_llm.side_effect = OutputLLMValidationError(
            "Invalid output schema."
        )

        response = self.client.post(
            "/api/export/csv",
            {"output_json": self._valid_output_json()},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue("detail" in response.data or "message" in response.data)

    @patch("file_processing.views.save_export_artifact", create=True)
    @patch("file_processing.views.generate_csv_download_artifact", create=True)
    @patch("file_processing.views.map_output_csv", create=True)
    @patch("file_processing.views.validate_output_llm", create=True)
    def test_export_csv_returns_500_when_filesystem_save_fails(
        self,
        mock_validate_output_llm,
        mock_map_output_csv,
        mock_generate_csv_download_artifact,
        mock_save_export_artifact,
    ):
        output_json = self._valid_output_json()
        mock_validate_output_llm.return_value = output_json
        mock_map_output_csv.return_value = {"sheets": []}
        mock_generate_csv_download_artifact.return_value = {
            "type": "csv",
            "name": "Sheet1.csv",
            "content": b"header\r\nvalue\r\n",
        }
        mock_save_export_artifact.side_effect = OSError("Disk write failed")

        response = self.client.post(
            "/api/export/csv",
            {"output_json": output_json},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertTrue("detail" in response.data or "message" in response.data)

    def test_export_csv_rejects_get(self):
        response = self.client.get("/api/export/csv")
        self.assertEqual(response.status_code, 405)
