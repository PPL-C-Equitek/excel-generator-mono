from django.test import SimpleTestCase

from file_processing.serializers import (
    CsvExportRequestSerializer,
    CsvExportResponseSerializer,
    ExcelExportRequestSerializer,
    ExcelExportResponseSerializer,
)


class CsvExportRequestSerializerTest(SimpleTestCase):
    def test_accepts_valid_output_json_object(self):
        serializer = CsvExportRequestSerializer(
            data={"output_json": {"document_info": {}, "summary": {}, "content_data": []}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_missing_output_json(self):
        serializer = CsvExportRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)

    def test_rejects_non_object_output_json(self):
        serializer = CsvExportRequestSerializer(data={"output_json": ["not-object"]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)

    def test_rejects_empty_output_json_object(self):
        serializer = CsvExportRequestSerializer(data={"output_json": {}})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)


class CsvExportResponseSerializerTest(SimpleTestCase):
    def _valid_metadata(self):
        return {
            "file_id": "csv_8fa2e3d1",
            "file_name": "export_123.csv",
            "artifact_type": "csv",
            "size_bytes": 128,
            "created_at": "2026-03-06T10:00:00Z",
        }

    def test_accepts_valid_response_metadata(self):
        serializer = CsvExportResponseSerializer(data=self._valid_metadata())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_invalid_artifact_type(self):
        payload = self._valid_metadata()
        payload["artifact_type"] = "txt"
        serializer = CsvExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("artifact_type", serializer.errors)

    def test_rejects_invalid_file_id_format(self):
        payload = self._valid_metadata()
        payload["file_id"] = "file_123"
        serializer = CsvExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_id", serializer.errors)

    def test_rejects_filename_with_path_separator(self):
        payload = self._valid_metadata()
        payload["file_name"] = "../export_123.csv"
        serializer = CsvExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_name", serializer.errors)

    def test_rejects_invalid_created_at(self):
        payload = self._valid_metadata()
        payload["created_at"] = "not-datetime"
        serializer = CsvExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("created_at", serializer.errors)


class ExcelExportRequestSerializerTest(SimpleTestCase):
    def test_accepts_valid_output_json_object(self):
        serializer = ExcelExportRequestSerializer(
            data={"output_json": {"document_info": {}, "summary": {}, "content_data": []}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_missing_output_json(self):
        serializer = ExcelExportRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)

    def test_rejects_non_object_output_json(self):
        serializer = ExcelExportRequestSerializer(data={"output_json": ["not-object"]})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)

    def test_rejects_empty_output_json_object(self):
        serializer = ExcelExportRequestSerializer(data={"output_json": {}})
        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)


class ExcelExportResponseSerializerTest(SimpleTestCase):
    def _valid_metadata(self):
        return {
            "file_id": "xlsx_8fa2e3d1",
            "file_name": "export_123.xlsx",
            "artifact_type": "xlsx",
            "size_bytes": 128,
            "created_at": "2026-03-29T10:00:00Z",
        }

    def test_accepts_valid_response_metadata(self):
        serializer = ExcelExportResponseSerializer(data=self._valid_metadata())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_invalid_artifact_type(self):
        payload = self._valid_metadata()
        payload["artifact_type"] = "csv"
        serializer = ExcelExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("artifact_type", serializer.errors)

    def test_rejects_invalid_file_id_format(self):
        payload = self._valid_metadata()
        payload["file_id"] = "file_123"
        serializer = ExcelExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_id", serializer.errors)

    def test_rejects_filename_with_path_separator(self):
        payload = self._valid_metadata()
        payload["file_name"] = "../export_123.xlsx"
        serializer = ExcelExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("file_name", serializer.errors)

    def test_rejects_negative_size_bytes(self):
        payload = self._valid_metadata()
        payload["size_bytes"] = -1
        serializer = ExcelExportResponseSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("size_bytes", serializer.errors)
