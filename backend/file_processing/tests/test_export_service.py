import csv
import io
import unittest
from copy import deepcopy
from unittest.mock import patch

import file_processing.services.export_service as export_service
from file_processing.services.export_service import (
    OutputCSVMappingError,
    OutputLLMValidationError,
    map_output_csv,
    validate_output_llm,
)


class ValidateOutputLLMTest(unittest.TestCase):
    def _build_valid_payload(self):
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

    def test_validate_output_llm_accepts_valid_ok_payload_single_sheet(self):
        output_json = self._build_valid_payload()

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_valid_multiple_sheets_payload(self):
        output_json = self._build_valid_payload()
        output_json["content_data"] = [
            {
                "table_name": "Sheet1_Januari",
                "headers": ["item_name", "quantity", "price"],
                "rows": [{"item_name": "Kertas", "quantity": 10, "price": 50000}],
            },
            {
                "table_name": "Sheet2_Februari",
                "headers": ["item_name", "quantity", "price"],
                "rows": [{"item_name": "Tinta", "quantity": 1, "price": 400000}],
            },
        ]

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_non_object_or_array_root(self):
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm("not-valid")

    def test_validate_output_llm_rejects_missing_required_top_level_keys(self):
        required_keys = ("document_info", "summary", "content_data")
        for key in required_keys:
            with self.subTest(missing_key=key):
                payload = self._build_valid_payload()
                payload.pop(key)
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_top_level_values(self):
        cases = [
            ("document_info_non_object", {"document_info": 1}),
            ("summary_non_object", {"summary": 123}),
            ("content_data_non_list", {"content_data": {}}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload.update(mutation)
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_document_info_fields(self):
        cases = [
            ("missing_source_type", {"filename": "laporan.xlsx"}),
            ("missing_filename", {"source_type": "Excel"}),
            ("source_type_non_string", {"source_type": 1, "filename": "laporan.xlsx"}),
            (
                "source_type_not_allowed",
                {"source_type": "Word", "filename": "laporan.xlsx"},
            ),
            ("filename_non_string", {"source_type": "Excel", "filename": 123}),
            ("filename_blank", {"source_type": "Excel", "filename": "   "}),
        ]
        for case_name, document_info in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["document_info"] = document_info
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_summary_values(self):
        payload = self._build_valid_payload()
        payload["summary"] = {
            "grand_total": 1500000,
            "period": {"year": "2026"},
        }
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm(payload)

        payload = self._build_valid_payload()
        payload["summary"] = {"": "blank-key"}
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm(payload)

        payload = self._build_valid_payload()
        payload["summary"] = {"grand_total": {1}}
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_content_data_structure(self):
        cases = [
            ("table_non_object", ["x"]),
            (
                "missing_table_name",
                [{"headers": ["item_name"], "rows": [{"item_name": "Kertas"}]}],
            ),
            (
                "missing_headers",
                [{"table_name": "Sheet1", "rows": [{"item_name": "Kertas"}]}],
            ),
            ("missing_rows", [{"table_name": "Sheet1", "headers": ["item_name"]}]),
            (
                "table_name_non_string",
                [{"table_name": 123, "headers": ["item_name"], "rows": [{"item_name": "Kertas"}]}],
            ),
            (
                "table_name_blank",
                [{"table_name": "   ", "headers": ["item_name"], "rows": [{"item_name": "Kertas"}]}],
            ),
            (
                "duplicate_table_name",
                [
                    {"table_name": "Sheet1", "headers": ["item_name"], "rows": [{"item_name": "Kertas"}]},
                    {"table_name": "Sheet1", "headers": ["item_name"], "rows": [{"item_name": "Pena"}]},
                ],
            ),
        ]
        for case_name, content_data in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["content_data"] = content_data
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_headers(self):
        cases = [
            ("headers_non_list", {"headers": "item_name"}),
            ("headers_empty", {"headers": []}),
            ("header_non_string", {"headers": ["item_name", 1]}),
            ("header_blank", {"headers": ["item_name", "   "]}),
            ("header_duplicate_case_insensitive", {"headers": ["Item", "item"]}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["content_data"][0].update(mutation)
                if case_name == "header_duplicate_case_insensitive":
                    payload["content_data"][0]["rows"] = [{"Item": "Kertas", "item": "Pena"}]
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_rows_container_and_row_type(self):
        cases = [
            ("rows_non_list", "not-list"),
            ("row_non_object", ["not-dict"]),
        ]
        for case_name, rows_value in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["content_data"][0]["rows"] = rows_value
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_row_header_mismatch_and_invalid_values(self):
        cases = [
            ("missing_required_header", [{"item_name": "Kertas", "quantity": 10}]),
            (
                "unknown_extra_header",
                [{"item_name": "Kertas", "quantity": 10, "price": 50000, "note": "x"}],
            ),
            (
                "nested_dict_value",
                [{"item_name": "Kertas", "quantity": 10, "price": {"raw": 50000}}],
            ),
            (
                "nested_list_value",
                [{"item_name": "Kertas", "quantity": 10, "price": [50000]}],
            ),
            (
                "non_scalar_value_type",
                [{"item_name": "Kertas", "quantity": 10, "price": {50000}}],
            ),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["content_data"][0]["rows"] = rows
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_allows_empty_rows_per_sheet(self):
        output_json = self._build_valid_payload()
        output_json["content_data"][0]["rows"] = []

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_unicode_and_formula_like_strings(self):
        output_json = self._build_valid_payload()
        output_json["content_data"][0] = {
            "table_name": "Sheet1_Januari",
            "headers": ["item_name", "note"],
            "rows": [{"item_name": "शोफ़ी", "note": "=SUM(A1:A2)"}],
        }

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"item_name": f"user-{index}", "quantity": index, "price": index})

        output_json = self._build_valid_payload()
        output_json["content_data"][0]["rows"] = rows

        result = validate_output_llm(output_json)

        self.assertEqual(len(result["content_data"][0]["rows"]), 1000)

    def test_validate_output_llm_rejects_empty_output_object(self):
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm({})


class MapOutputCSVTest(unittest.TestCase):
    def _build_validated_output(self):
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

    def test_mapping_output_csv_maps_single_sheet_successfully(self):
        validated_output = self._build_validated_output()

        result = map_output_csv(validated_output)

        self.assertEqual(result["document_info"], validated_output["document_info"])
        self.assertEqual(result["summary"], validated_output["summary"])
        self.assertEqual(result["sheets"][0]["name"], "Sheet1_Januari")
        self.assertEqual(
            result["sheets"][0]["headers"],
            ["item_name", "quantity", "price"],
        )
        self.assertEqual(
            result["sheets"][0]["rows"],
            [["Kertas", 10, 50000], ["Pena", 5, 10000]],
        )

    def test_mapping_output_csv_maps_multiple_sheets_successfully(self):
        validated_output = self._build_validated_output()
        validated_output["content_data"].append(
            {
                "table_name": "Sheet2_Februari",
                "headers": ["item_name", "quantity", "price"],
                "rows": [{"item_name": "Tinta", "quantity": 1, "price": 400000}],
            }
        )

        result = map_output_csv(validated_output)

        self.assertEqual(len(result["sheets"]), 2)
        self.assertEqual(
            result["sheets"][1]["headers"],
            ["item_name", "quantity", "price"],
        )
        self.assertEqual(result["sheets"][1]["rows"], [["Tinta", 1, 400000]])

    def test_mapping_output_csv_allows_empty_rows(self):
        validated_output = self._build_validated_output()
        validated_output["content_data"][0]["rows"] = []

        result = map_output_csv(validated_output)

        self.assertEqual(
            result["sheets"][0]["headers"],
            ["item_name", "quantity", "price"],
        )
        self.assertEqual(result["sheets"][0]["rows"], [])

    def test_mapping_output_csv_keeps_unicode_and_formula_like_values(self):
        validated_output = self._build_validated_output()
        validated_output["content_data"][0]["headers"] = ["item_name", "note"]
        validated_output["content_data"][0]["rows"] = [
            {"item_name": "शोफ़ी", "note": "=SUM(A1:A2)"},
        ]

        result = map_output_csv(validated_output)

        self.assertEqual(result["sheets"][0]["rows"], [["शोफ़ी", "=SUM(A1:A2)"]])

    def test_mapping_output_csv_rejects_invalid_root_or_sheets(self):
        cases = [
            ("root_non_object", "invalid"),
            ("sheets_missing", {"status": "ok"}),
            ("content_data_non_list", {"content_data": {}}),
            ("table_item_non_object", {"content_data": ["invalid"]}),
        ]
        for case_name, payload in cases:
            with self.subTest(case=case_name):
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(payload)

    def test_mapping_output_csv_rejects_sheet_missing_required_fields(self):
        cases = [
            (
                "missing_table_name",
                {"headers": ["item_name"], "rows": [{"item_name": "Kertas"}]},
            ),
            (
                "missing_headers",
                {"table_name": "Sheet1_Januari", "rows": [{"item_name": "Kertas"}]},
            ),
            ("missing_rows", {"table_name": "Sheet1_Januari", "headers": ["item_name"]}),
        ]
        for case_name, table_payload in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["content_data"] = [table_payload]
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(validated_output)

    def test_mapping_output_csv_rejects_invalid_columns_and_rows_container(self):
        cases = [
            ("headers_non_list", {"headers": "item_name"}),
            ("headers_empty", {"headers": []}),
            ("rows_non_list", {"rows": "not-list"}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["content_data"][0].update(mutation)
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(validated_output)

    def test_mapping_output_csv_rejects_invalid_row_items_and_key_mismatch(self):
        cases = [
            ("row_non_object", ["not-dict"]),
            ("missing_column", [{"item_name": "Kertas", "quantity": 10}]),
            (
                "unknown_column",
                [{"item_name": "Kertas", "quantity": 10, "price": 50000, "zip": 12345}],
            ),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["content_data"][0]["rows"] = rows
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(validated_output)

    def test_mapping_output_csv_does_not_mutate_input_payload(self):
        validated_output = self._build_validated_output()
        original = deepcopy(validated_output)

        _ = map_output_csv(validated_output)

        self.assertEqual(validated_output, original)

    def test_mapping_output_csv_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append(
                {"item_name": f"user-{index}", "quantity": index, "price": index}
            )

        validated_output = self._build_validated_output()
        validated_output["content_data"][0]["rows"] = rows

        result = map_output_csv(validated_output)

        self.assertEqual(len(result["sheets"][0]["rows"]), 1000)

    def test_mapping_output_csv_uses_stubbed_row_mapper(self):
        validated_output = self._build_validated_output()
        stubbed_rows = [["stubbed-row"]]

        with patch(
            "file_processing.services.export_service._map_rows",
            return_value=stubbed_rows,
        ) as mocked_map_rows:
            result = map_output_csv(validated_output)

        mocked_map_rows.assert_called_once_with(
            headers=["item_name", "quantity", "price"],
            rows=validated_output["content_data"][0]["rows"],
            table_index=0,
        )
        self.assertEqual(result["sheets"][0]["rows"], stubbed_rows)


class GenerateCSVTest(unittest.TestCase):
    class PrefixSanitizationPolicy:
        def sanitize_header(self, header):
            return f"HDR::{header}"

        def sanitize_value(self, value):
            if isinstance(value, str):
                return f"VAL::{value}"
            return value

    class PrefixFileNamePolicy:
        def build_filename(self, sheet_name):
            return f"csv_{sheet_name.lower()}.export.csv"

    class BlankFileNamePolicy:
        def build_filename(self, sheet_name):
            return "   "

    def _build_mapped_output(self):
        return {
            "sheets": [
                {
                    "name": "Sheet1",
                    "headers": ["name", "age", "city"],
                    "rows": [
                        ["Zufar", 21, "Depok"],
                        ["Siti", 22, "Jakarta"],
                    ],
                }
            ]
        }

    def _read_csv_rows(self, csv_content):
        return list(csv.reader(io.StringIO(csv_content)))

    def test_generate_csv_exposes_expected_api(self):
        self.assertTrue(
            hasattr(export_service, "generate_csv"),
            "generate_csv must be implemented in export_service.",
        )
        self.assertTrue(
            hasattr(export_service, "OutputCSVGenerationError"),
            "OutputCSVGenerationError must be implemented in export_service.",
        )

    def test_generate_csv_single_sheet_successfully(self):
        mapped_output = self._build_mapped_output()

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["name"], "Sheet1.csv")
        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [
                ["name", "age", "city"],
                ["Zufar", "21", "Depok"],
                ["Siti", "22", "Jakarta"],
            ],
        )

    def test_generate_csv_multiple_sheets_successfully(self):
        mapped_output = self._build_mapped_output()
        mapped_output["sheets"].append(
            {
                "name": "Sheet2",
                "headers": ["sku", "price"],
                "rows": [["A-1", 15000]],
            }
        )

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(result["files"][0]["name"], "Sheet1.csv")
        self.assertEqual(result["files"][1]["name"], "Sheet2.csv")
        self.assertEqual(
            self._read_csv_rows(result["files"][1]["content"]),
            [
                ["sku", "price"],
                ["A-1", "15000"],
            ],
        )

    def test_generate_csv_allows_empty_rows(self):
        mapped_output = self._build_mapped_output()
        mapped_output["sheets"][0]["rows"] = []

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [["name", "age", "city"]],
        )

    def test_generate_csv_rejects_invalid_root_or_sheets(self):
        cases = [
            ("root_non_object", "invalid"),
            ("sheets_missing", {}),
            ("sheets_non_list", {"sheets": {}}),
            ("sheet_non_object", {"sheets": ["invalid"]}),
        ]
        for case_name, payload in cases:
            with self.subTest(case=case_name):
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(payload)

    def test_generate_csv_rejects_sheet_missing_required_fields(self):
        cases = [
            ("missing_name", {"headers": ["name"], "rows": [["Zufar"]]}),
            ("missing_headers", {"name": "Sheet1", "rows": [["Zufar"]]}),
            ("missing_rows", {"name": "Sheet1", "headers": ["name"]}),
        ]
        for case_name, sheet_payload in cases:
            with self.subTest(case=case_name):
                mapped_output = {"sheets": [sheet_payload]}
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(mapped_output)

    def test_generate_csv_rejects_invalid_sheet_name(self):
        cases = [
            ("name_non_string", 123),
            ("name_blank", "   "),
        ]
        for case_name, name_value in cases:
            with self.subTest(case=case_name):
                mapped_output = self._build_mapped_output()
                mapped_output["sheets"][0]["name"] = name_value
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(mapped_output)

    def test_generate_csv_rejects_invalid_headers_and_rows(self):
        cases = [
            ("headers_non_list", {"headers": "name"}),
            ("headers_empty", {"headers": []}),
            ("header_non_string", {"headers": ["name", 1]}),
            ("rows_non_list", {"rows": "not-list"}),
            ("row_non_list", {"rows": ["not-list-row"]}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                mapped_output = self._build_mapped_output()
                mapped_output["sheets"][0].update(mutation)
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(mapped_output)

    def test_generate_csv_rejects_blank_or_duplicate_headers(self):
        cases = [
            ("blank_header", ["name", "   "], [["Zufar", "x"]]),
            ("duplicate_header_case_insensitive", ["Name", "name"], [["Zufar", "x"]]),
        ]
        for case_name, headers, rows in cases:
            with self.subTest(case=case_name):
                mapped_output = self._build_mapped_output()
                mapped_output["sheets"][0]["headers"] = headers
                mapped_output["sheets"][0]["rows"] = rows
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(mapped_output)

    def test_generate_csv_rejects_row_length_mismatch(self):
        mapped_output = self._build_mapped_output()
        mapped_output["sheets"][0]["rows"] = [["Zufar", 21]]

        with self.assertRaises(export_service.OutputCSVGenerationError):
            export_service.generate_csv(mapped_output)

    def test_generate_csv_rejects_nested_or_unsupported_row_values(self):
        cases = [
            ("nested_dict_value", [["Zufar", {"age": 21}, "Depok"]]),
            ("nested_list_value", [["Zufar", [21], "Depok"]]),
            ("unsupported_set_value", [["Zufar", {21}, "Depok"]]),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                mapped_output = self._build_mapped_output()
                mapped_output["sheets"][0]["rows"] = rows
                with self.assertRaises(export_service.OutputCSVGenerationError):
                    export_service.generate_csv(mapped_output)

    def test_generate_csv_handles_csv_special_characters(self):
        mapped_output = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "headers": ["text"],
                    "rows": [['Hello, "CSV"\nWorld']],
                }
            ]
        }

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [["text"], ['Hello, "CSV"\nWorld']],
        )

    def test_generate_csv_keeps_unicode_and_sanitizes_formula_like_values(self):
        mapped_output = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "headers": ["name", "note"],
                    "rows": [["शोफ़ी", "=SUM(A1:A2)"]],
                }
            ]
        }

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [["name", "note"], ["शोफ़ी", "'=SUM(A1:A2)"]],
        )

    def test_generate_csv_sanitizes_formula_like_values_to_prevent_csv_injection(self):
        dangerous_values = [
            "=SUM(A1:A2)",
            "+CMD|'/C calc'!A0",
            "-10+20",
            "@HYPERLINK(\"http://evil.com\")",
        ]

        for value in dangerous_values:
            with self.subTest(value=value):
                mapped_output = {
                    "sheets": [
                        {
                            "name": "Sheet1",
                            "headers": ["name", "note"],
                            "rows": [["Zufar", value]],
                        }
                    ]
                }

                result = export_service.generate_csv(mapped_output)
                rows = self._read_csv_rows(result["files"][0]["content"])

                self.assertEqual(rows[1][1], f"'{value}")

    def test_generate_csv_keeps_whitespace_only_and_prequoted_values_unchanged(self):
        mapped_output = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "headers": ["note", "formula"],
                    "rows": [["   ", "'=SUM(A1:A2)"]],
                }
            ]
        }

        result = export_service.generate_csv(mapped_output)

        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [["note", "formula"], ["   ", "'=SUM(A1:A2)"]],
        )

    def test_generate_csv_sanitizes_formula_like_headers_to_prevent_csv_injection(self):
        mapped_output = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "headers": ["=InjectedHeader", "name"],
                    "rows": [["x", "Zufar"]],
                }
            ]
        }

        result = export_service.generate_csv(mapped_output)
        rows = self._read_csv_rows(result["files"][0]["content"])

        self.assertEqual(rows[0][0], "'=InjectedHeader")

    def test_generate_csv_uses_mocked_csv_builder(self):
        mapped_output = self._build_mapped_output()
        mocked_csv_content = "name,age,city\r\nstub,0,stub-city\r\n"

        with patch(
            "file_processing.services.export_service._build_csv_content",
            return_value=mocked_csv_content,
        ) as mocked_builder:
            result = export_service.generate_csv(mapped_output)

        mocked_builder.assert_called_once_with(
            ["name", "age", "city"],
            [["Zufar", 21, "Depok"], ["Siti", 22, "Jakarta"]],
        )
        self.assertEqual(result["files"][0]["content"], mocked_csv_content)

    def test_generate_csv_supports_custom_sanitization_policy(self):
        mapped_output = self._build_mapped_output()
        policy = self.PrefixSanitizationPolicy()

        result = export_service.generate_csv(
            mapped_output,
            sanitization_policy=policy,
        )

        self.assertEqual(
            self._read_csv_rows(result["files"][0]["content"]),
            [
                ["HDR::name", "HDR::age", "HDR::city"],
                ["VAL::Zufar", "21", "VAL::Depok"],
                ["VAL::Siti", "22", "VAL::Jakarta"],
            ],
        )

    def test_generate_csv_rejects_invalid_sanitization_policy_contract(self):
        mapped_output = self._build_mapped_output()

        with self.assertRaises(export_service.OutputCSVGenerationError):
            export_service.generate_csv(
                mapped_output,
                sanitization_policy=object(),
            )

    def test_generate_csv_supports_custom_filename_policy(self):
        mapped_output = self._build_mapped_output()
        filename_policy = self.PrefixFileNamePolicy()

        result = export_service.generate_csv(
            mapped_output,
            filename_policy=filename_policy,
        )

        self.assertEqual(result["files"][0]["name"], "csv_sheet1.export.csv")

    def test_generate_csv_rejects_invalid_filename_policy_contract(self):
        mapped_output = self._build_mapped_output()

        with self.assertRaises(export_service.OutputCSVGenerationError):
            export_service.generate_csv(
                mapped_output,
                filename_policy=object(),
            )

    def test_generate_csv_rejects_blank_filename_from_policy(self):
        mapped_output = self._build_mapped_output()
        filename_policy = self.BlankFileNamePolicy()

        with self.assertRaises(export_service.OutputCSVGenerationError):
            export_service.generate_csv(
                mapped_output,
                filename_policy=filename_policy,
            )


if __name__ == "__main__":
    unittest.main()
