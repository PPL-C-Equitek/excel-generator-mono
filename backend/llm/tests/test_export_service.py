import json
from unittest.mock import patch
from django.test import SimpleTestCase

from llm.services.export_service import (
    _collect_rows_array_metadata,
    _extract_document_type,
    _resolve_export_source_type,
    _to_scalar_cell,
    build_export_output_json,
    extract_original_name,
)

class ExportServiceTest(SimpleTestCase):
    def test_extract_original_name_uses_input_document_info_filename(self):
        result = extract_original_name(
            {"document_info": {"filename": "input-doc.pdf"}},
            {"document_info": {"filename": "output-doc.pdf"}},
        )

        self.assertEqual(result, "input-doc.pdf")

    def test_extract_original_name_falls_back_to_output_document_info_filename(self):
        result = extract_original_name(
            {"document_info": {}},
            {"document_info": {"filename": "output-doc.pdf"}},
        )

        self.assertEqual(result, "output-doc.pdf")

    def test_extract_original_name_returns_generated_output_when_no_filename_available(self):
        result = extract_original_name(
            {"document_info": {}},
            {"document_info": {}},
        )

        self.assertEqual(result, "generated-output")

    def test_extract_original_name_returns_generated_output_when_input_and_output_are_not_objects(self):
        result = extract_original_name([], [])

        self.assertEqual(result, "generated-output")

    def test_extract_original_name_returns_generated_output_when_document_info_values_are_not_objects(self):
        result = extract_original_name(
            {"document_info": "not-an-object"},
            {"document_info": "not-an-object"},
        )

        self.assertEqual(result, "generated-output")

    def test_extract_document_type_returns_unknown_for_non_object_payload(self):
        result = _extract_document_type(["not-an-object"])

        self.assertEqual(result, "unknown")

    def test_extract_document_type_supports_file_type_and_format_keys(self):
        file_type_result = _extract_document_type({"file_type": " XLSX "})
        format_result = _extract_document_type({"format": " CSV "})

        self.assertEqual(file_type_result, "xlsx")
        self.assertEqual(format_result, "csv")

    def test_build_export_output_json_normalizes_headers_and_rows_payload(self):
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000], ["ER", 1500]],
            "final_answer": "ignored for export payload",
        }
        input_json = {
            "filename": "hospital-report.xlsx",
            "document_info": {"source_type": "Excel"},
        }

        export_output_json = build_export_output_json(
            input_json=input_json,
            output_json=raw_output_json,
        )

        self.assertEqual(
            export_output_json,
            {
                "document_info": {
                    "source_type": "Excel",
                    "filename": "hospital-report.xlsx",
                },
                "summary": {
                    "total_tables": 1,
                    "total_rows": 2,
                    "total_columns": 2,
                },
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["unit", "value"],
                        "rows": [
                            {"unit": "ICU", "value": 1000},
                            {"unit": "ER", "value": 1500},
                        ],
                    }
                ],
            },
        )

    def test_build_export_output_json_normalizes_sheet_like_mapping_payload(self):
        raw_output_json = {
            "Rawat Jalan": [
                {"unit": "Rawat Jalan", "value": 1000},
                {"unit": "Rawat Jalan", "value": 1200},
            ],
            "ICU": [
                {"unit": "ICU", "value": 3000},
            ],
        }
        input_json = {
            "document_info": {
                "filename": "finance.pdf",
                "source_type": "PDF",
            }
        }

        export_output_json = build_export_output_json(
            input_json=input_json,
            output_json=raw_output_json,
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "PDF",
                "filename": "finance.pdf",
            },
        )
        self.assertEqual(
            export_output_json["summary"],
            {
                "total_tables": 2,
                "total_rows": 3,
                "total_columns": 2,
            },
        )
        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Rawat Jalan",
                    "headers": ["unit", "value"],
                    "rows": [
                        {"unit": "Rawat Jalan", "value": 1000},
                        {"unit": "Rawat Jalan", "value": 1200},
                    ],
                },
                {
                    "table_name": "ICU",
                    "headers": ["unit", "value"],
                    "rows": [
                        {"unit": "ICU", "value": 3000},
                    ],
                },
            ],
        )

    def test_build_export_output_json_infers_pdf_source_type_from_filename(self):
        export_output_json = build_export_output_json(
            input_json={"document_info": {"filename": "invoice.pdf"}},
            output_json={"headers": ["unit"], "rows": [["ICU"]]},
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "PDF",
                "filename": "invoice.pdf",
            },
        )

    def test_build_export_output_json_falls_back_to_excel_when_source_type_is_unrecognized(self):
        export_output_json = build_export_output_json(
            input_json={
                "document_info": {
                    "filename": "invoice.docx",
                    "source_type": "word",
                }
            },
            output_json={"headers": ["unit"], "rows": [["ICU"]]},
        )

        self.assertEqual(
            export_output_json["document_info"],
            {
                "source_type": "Excel",
                "filename": "invoice.docx",
            },
        )

    def test_build_export_output_json_normalizes_duplicate_blank_headers_and_mixed_rows(self):
        export_output_json = build_export_output_json(
            input_json={"document_info": {"source_type": "xlsx"}},
            output_json={
                "headers": [" Unit ", "", "unit"],
                "rows": [
                    ["ICU", 10, 20],
                    {"Unit": "ER", "column_2": 30, "unit_2": 40},
                    "fallback",
                ],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["Unit", "column_2", "unit_2"],
                    "rows": [
                        {"Unit": "ICU", "column_2": 10, "unit_2": 20},
                        {"Unit": "ER", "column_2": 30, "unit_2": 40},
                        {"Unit": "fallback", "column_2": None, "unit_2": None},
                    ],
                }
            ],
        )

    def test_build_export_output_json_uses_sheet_fallback_name_for_blank_sheet_key(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json={
                "   ": [1, 2],
                "Named": [{"value": 3, "other": "ok"}],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": 1}, {"value": 2}],
                },
                {
                    "table_name": "Named",
                    "headers": ["value", "other"],
                    "rows": [{"value": 3, "other": "ok"}],
                },
            ],
        )

    def test_build_export_output_json_wraps_scalar_payload_in_default_value_table(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json=123,
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": 123}],
                }
            ],
        )
        self.assertEqual(
            export_output_json["summary"],
            {"total_tables": 1, "total_rows": 1, "total_columns": 1},
        )

    def test_build_export_output_json_uses_default_value_header_for_empty_headers(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json={
                "headers": [],
                "rows": [[{"bad"}]],
            },
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["value"],
                    "rows": [{"value": "[Unserializable Value]"}],
                }
            ],
        )

    def test_build_export_output_json_infers_headers_from_list_of_lists_payload(self):
        export_output_json = build_export_output_json(
            input_json={"filename": "summary.xlsx"},
            output_json=[["ICU", 10], ["ER", 20]],
        )

        self.assertEqual(
            export_output_json["content_data"],
            [
                {
                    "table_name": "Sheet1",
                    "headers": ["column_1", "column_2"],
                    "rows": [
                        {"column_1": "ICU", "column_2": 10},
                        {"column_1": "ER", "column_2": 20},
                    ],
                }
            ],
        )

    def test_build_export_output_json_reuses_cached_serialization_for_repeated_nested_cell_values(self):
        shared_value = {"unit": "ICU", "meta": {"active": True}}

        with patch("llm.services.export_service.json.dumps", wraps=json.dumps) as mock_json_dumps:
            export_output_json = build_export_output_json(
                input_json={"filename": "summary.xlsx"},
                output_json={
                    "headers": ["payload"],
                    "rows": [
                        [shared_value],
                        [shared_value],
                        [shared_value],
                    ],
                },
            )

        self.assertEqual(
            export_output_json["content_data"][0]["rows"],
            [
                {"payload": json.dumps(shared_value)},
                {"payload": json.dumps(shared_value)},
                {"payload": json.dumps(shared_value)},
            ],
        )
        self.assertEqual(mock_json_dumps.call_count, 1)

    def test_build_export_output_json_serializes_repeated_bytes_cells_once_with_cache(self):
        shared_value = b"ICU"

        with patch("llm.services.export_service.json.dumps", wraps=json.dumps) as mock_json_dumps:
            export_output_json = build_export_output_json(
                input_json={"filename": "summary.xlsx"},
                output_json={
                    "headers": ["payload"],
                    "rows": [
                        [shared_value],
                        [shared_value],
                    ],
                },
            )

        self.assertEqual(
            export_output_json["content_data"][0]["rows"],
            [
                {"payload": "b'ICU'"},
                {"payload": "b'ICU'"},
            ],
        )
        self.assertEqual(mock_json_dumps.call_count, 0)

    def test_to_scalar_cell_serializes_nested_object_without_cache(self):
        payload = {"unit": "ICU", "meta": {"active": True}}

        with patch("llm.services.export_service.json.dumps", wraps=json.dumps) as mock_json_dumps:
            result = _to_scalar_cell(payload)

        self.assertEqual(result, json.dumps(payload))
        self.assertEqual(mock_json_dumps.call_count, 1)

    def test_to_scalar_cell_returns_bytes_as_string_without_cache(self):
        result = _to_scalar_cell(b"ICU")

        self.assertEqual(result, "b'ICU'")


class ResolveExportSourceTypeTest(SimpleTestCase):
    def test_positive_reads_source_type_from_input_json(self):
        result = _resolve_export_source_type(
            {"document_info": {"source_type": "PDF"}},
            {},
        )
        self.assertEqual(result, "PDF")

    def test_positive_falls_back_to_output_json_when_input_json_has_no_source_type(self):
        result = _resolve_export_source_type(
            {},
            {"document_info": {"source_type": "PDF"}},
        )
        self.assertEqual(result, "PDF")

    def test_positive_input_json_source_type_takes_priority_over_output_json(self):
        result = _resolve_export_source_type(
            {"document_info": {"source_type": "Excel"}},
            {"document_info": {"source_type": "PDF"}},
        )
        self.assertEqual(result, "Excel")

    def test_positive_falls_back_to_filename_extension_when_both_json_missing_source_type(self):
        result = _resolve_export_source_type(
            {"filename": "report.pdf"},
            {},
        )
        self.assertEqual(result, "PDF")

    def test_negative_defaults_to_excel_when_no_source_type_info_available(self):
        result = _resolve_export_source_type({}, {})
        self.assertEqual(result, "Excel")


class CollectRowsArrayMetadataShortCircuitTest(SimpleTestCase):
    def test_edge_breaks_early_on_mixed_type_rows(self):
        rows = [{"a": 1}, [1, 2], {"b": 3}]
        all_lists, all_dicts, _, collected_headers = _collect_rows_array_metadata(rows)

        self.assertFalse(all_lists)
        self.assertFalse(all_dicts)
        self.assertEqual(collected_headers, ["a"])

    def test_positive_all_dicts_collects_all_headers(self):
        rows = [{"a": 1}, {"b": 2}, {"a": 3, "c": 4}]
        all_lists, all_dicts, _, collected_headers = _collect_rows_array_metadata(rows)

        self.assertFalse(all_lists)
        self.assertTrue(all_dicts)
        self.assertEqual(collected_headers, ["a", "b", "c"])

    def test_positive_all_lists_tracks_max_columns(self):
        rows = [[1, 2], [3, 4, 5], [6]]
        all_lists, all_dicts, max_columns, _ = _collect_rows_array_metadata(rows)

        self.assertTrue(all_lists)
        self.assertFalse(all_dicts)
        self.assertEqual(max_columns, 3)

