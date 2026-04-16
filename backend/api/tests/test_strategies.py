from django.test import SimpleTestCase

from api.strategies.artifact_formats import (
    ArtifactFormatRegistry,
    ArtifactFormatStrategy,
    CsvFormatStrategy,
    ExcelFormatStrategy,
)


class ArtifactFormatStrategyBaseTest(SimpleTestCase):
    def test_abstract_export_storage_dir_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            ArtifactFormatStrategy.export_storage_dir(object())

    def test_abstract_resolve_history_content_type_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            ArtifactFormatStrategy.resolve_history_content_type(object(), "csv")

    def test_abstract_export_to_filesystem_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            ArtifactFormatStrategy.export_to_filesystem(object(), {"ok": True})

    def test_abstract_resolve_direct_download_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            ArtifactFormatStrategy.resolve_direct_download(object(), "id")


class CsvFormatStrategyTest(SimpleTestCase):
    def test_export_storage_dir_returns_configured_directory(self):
        strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )

        self.assertEqual(strategy.export_storage_dir(), "/tmp/csv")

    def test_resolve_history_content_type_returns_zip_for_zip_artifact(self):
        strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )

        self.assertEqual(strategy.resolve_history_content_type("zip"), "application/zip")

    def test_resolve_history_content_type_returns_csv_for_non_zip_artifact(self):
        strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )

        self.assertEqual(strategy.resolve_history_content_type("csv"), "text/csv")

    def test_export_to_filesystem_forwards_output_json_and_storage_dir(self):
        captured = {}

        def _export_to_filesystem(**kwargs):
            captured.update(kwargs)
            return {"file_name": "export.csv"}

        strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=_export_to_filesystem,
            resolve_direct_download=lambda **_: None,
        )

        result = strategy.export_to_filesystem({"sheet": 1})

        self.assertEqual(result, {"file_name": "export.csv"})
        self.assertEqual(captured, {"output_json": {"sheet": 1}, "storage_dir": "/tmp/csv"})

    def test_resolve_direct_download_forwards_file_id_and_storage_dir(self):
        captured = {}

        def _resolve_direct_download(**kwargs):
            captured.update(kwargs)
            return {"file_name": "export.csv"}

        strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=_resolve_direct_download,
        )

        result = strategy.resolve_direct_download("csv_token")

        self.assertEqual(result, {"file_name": "export.csv"})
        self.assertEqual(captured, {"file_id": "csv_token", "storage_dir": "/tmp/csv"})


class ExcelFormatStrategyTest(SimpleTestCase):
    def test_export_storage_dir_returns_configured_directory(self):
        strategy = ExcelFormatStrategy(
            storage_dir="/tmp/excel",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )

        self.assertEqual(strategy.export_storage_dir(), "/tmp/excel")

    def test_resolve_history_content_type_returns_excel_mime_type(self):
        strategy = ExcelFormatStrategy(
            storage_dir="/tmp/excel",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )

        self.assertEqual(
            strategy.resolve_history_content_type("xlsx"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_export_to_filesystem_forwards_output_json_and_storage_dir(self):
        captured = {}

        def _export_to_filesystem(**kwargs):
            captured.update(kwargs)
            return {"file_name": "export.xlsx"}

        strategy = ExcelFormatStrategy(
            storage_dir="/tmp/excel",
            export_to_filesystem=_export_to_filesystem,
            resolve_direct_download=lambda **_: None,
        )

        result = strategy.export_to_filesystem({"sheet": 1})

        self.assertEqual(result, {"file_name": "export.xlsx"})
        self.assertEqual(captured, {"output_json": {"sheet": 1}, "storage_dir": "/tmp/excel"})

    def test_resolve_direct_download_forwards_export_id_and_storage_dir(self):
        captured = {}

        def _resolve_direct_download(**kwargs):
            captured.update(kwargs)
            return {"file_name": "export.xlsx"}

        strategy = ExcelFormatStrategy(
            storage_dir="/tmp/excel",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=_resolve_direct_download,
        )

        result = strategy.resolve_direct_download("xlsx_token")

        self.assertEqual(result, {"file_name": "export.xlsx"})
        self.assertEqual(captured, {"export_id": "xlsx_token", "storage_dir": "/tmp/excel"})


class ArtifactFormatRegistryTest(SimpleTestCase):
    def test_get_returns_registered_strategy(self):
        csv_strategy = CsvFormatStrategy(
            storage_dir="/tmp/csv",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )
        xlsx_strategy = ExcelFormatStrategy(
            storage_dir="/tmp/excel",
            export_to_filesystem=lambda **_: None,
            resolve_direct_download=lambda **_: None,
        )
        registry = ArtifactFormatRegistry([csv_strategy, xlsx_strategy])

        self.assertIs(registry.get("csv"), csv_strategy)
        self.assertIs(registry.get("xlsx"), xlsx_strategy)
