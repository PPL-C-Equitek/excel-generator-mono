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
            "status": "ok",
            "summary": "Successfully extracted rows.",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "age"],
                    "rows": [
                        {"name": "Zufar", "age": 21},
                        {"name": "Siti", "age": 22},
                    ],
                }
            ],
            "validations": [
                {"sheet": "Sheet1", "rule": "row_count>0", "level": "info"},
            ],
            "errors": [],
        }

    def test_validate_output_llm_accepts_valid_ok_payload_single_sheet(self):
        output_json = self._build_valid_payload()

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_valid_error_payload(self):
        output_json = {
            "status": "error",
            "summary": "Extraction failed for uploaded file.",
            "sheets": [],
            "validations": [],
            "errors": ["Unsupported file structure"],
        }

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_valid_multiple_sheets_payload(self):
        output_json = self._build_valid_payload()
        output_json["sheets"] = [
            {
                "name": "Employees",
                "columns": ["name", "age"],
                "rows": [{"name": "Zufar", "age": 21}],
            },
            {
                "name": "Products",
                "columns": ["sku", "price"],
                "rows": [{"sku": "A-1", "price": 15000}],
            },
        ]
        output_json["validations"] = [
            {"sheet": "Employees", "rule": "row_count>0", "level": "warning"}
        ]

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_non_object_or_array_root(self):
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm("not-valid")

    def test_validate_output_llm_rejects_missing_required_top_level_keys(self):
        required_keys = ("status", "summary", "sheets", "validations", "errors")
        for key in required_keys:
            with self.subTest(missing_key=key):
                payload = self._build_valid_payload()
                payload.pop(key)
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_top_level_values(self):
        cases = [
            ("status_non_string", {"status": 1}),
            ("status_not_allowed", {"status": "partial"}),
            ("summary_non_string", {"summary": 123}),
            ("sheets_non_list", {"sheets": {}}),
            ("validations_non_list", {"validations": {}}),
            ("errors_non_list", {"errors": {}}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload.update(mutation)
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_sheet_structure(self):
        cases = [
            ("sheet_non_object", ["x"]),
            ("missing_name", [{"columns": ["name"], "rows": [{"name": "Zufar"}]}]),
            ("missing_columns", [{"name": "Sheet1", "rows": [{"name": "Zufar"}]}]),
            ("missing_rows", [{"name": "Sheet1", "columns": ["name"]}]),
            (
                "sheet_name_non_string",
                [{"name": 123, "columns": ["name"], "rows": [{"name": "Zufar"}]}],
            ),
            (
                "sheet_name_blank",
                [{"name": "   ", "columns": ["name"], "rows": [{"name": "Zufar"}]}],
            ),
            (
                "duplicate_sheet_name",
                [
                    {"name": "Sheet1", "columns": ["name"], "rows": [{"name": "Zufar"}]},
                    {"name": "Sheet1", "columns": ["name"], "rows": [{"name": "Siti"}]},
                ],
            ),
        ]
        for case_name, sheets in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["sheets"] = sheets
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_columns(self):
        cases = [
            ("columns_non_list", {"columns": "name"}),
            ("columns_empty", {"columns": []}),
            ("column_non_string", {"columns": ["name", 1]}),
            ("column_blank", {"columns": ["name", "   "]}),
            ("column_duplicate_case_insensitive", {"columns": ["Name", "name"]}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["sheets"][0].update(mutation)
                if case_name == "column_duplicate_case_insensitive":
                    payload["sheets"][0]["rows"] = [{"Name": "Zufar", "name": "Zufar"}]
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
                payload["sheets"][0]["rows"] = rows_value
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_row_column_mismatch_and_invalid_values(self):
        cases = [
            ("missing_required_column", [{"name": "Zufar"}]),
            ("unknown_extra_column", [{"name": "Zufar", "age": 21, "city": "Depok"}]),
            ("nested_dict_value", [{"name": "Zufar", "age": {"raw": 21}}]),
            ("nested_list_value", [{"name": "Zufar", "age": [21]}]),
            ("non_scalar_value_type", [{"name": "Zufar", "age": {21}}]),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["sheets"][0]["rows"] = rows
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_validation_item_structure(self):
        cases = [
            ("validation_non_object", ["bad-item"]),
            ("validation_missing_sheet", [{"rule": "must_have_name", "level": "info"}]),
            ("validation_missing_rule", [{"sheet": "Sheet1", "level": "info"}]),
            ("validation_missing_level", [{"sheet": "Sheet1", "rule": "must_have_name"}]),
        ]
        for case_name, validations in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["validations"] = validations
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_validation_fields(self):
        cases = [
            ("validation_sheet_non_string", [{"sheet": 1, "rule": "r", "level": "info"}]),
            ("validation_sheet_blank", [{"sheet": "  ", "rule": "r", "level": "info"}]),
            ("validation_sheet_unknown", [{"sheet": "Unknown", "rule": "r", "level": "info"}]),
            ("validation_rule_non_string", [{"sheet": "Sheet1", "rule": 1, "level": "info"}]),
            ("validation_rule_blank", [{"sheet": "Sheet1", "rule": " ", "level": "info"}]),
            ("validation_level_non_string", [{"sheet": "Sheet1", "rule": "r", "level": 1}]),
            (
                "validation_level_not_allowed",
                [{"sheet": "Sheet1", "rule": "r", "level": "critical"}],
            ),
        ]
        for case_name, validations in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["validations"] = validations
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_rejects_non_string_error_items(self):
        cases = [
            ["error-1", 2],
            [False],
            [None],
        ]
        for errors in cases:
            with self.subTest(errors=errors):
                payload = self._build_valid_payload()
                payload["status"] = "error"
                payload["errors"] = errors
                with self.assertRaises(OutputLLMValidationError):
                    validate_output_llm(payload)

    def test_validate_output_llm_allows_empty_rows_per_sheet(self):
        output_json = self._build_valid_payload()
        output_json["sheets"][0]["rows"] = []

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_unicode_and_formula_like_strings(self):
        output_json = self._build_valid_payload()
        output_json["sheets"][0] = {
            "name": "Sheet1",
            "columns": ["name", "note"],
            "rows": [{"name": "शोफ़ी", "note": "=SUM(A1:A2)"}],
        }
        output_json["validations"] = []

        result = validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"name": f"user-{index}", "age": index})

        output_json = self._build_valid_payload()
        output_json["sheets"][0]["rows"] = rows
        output_json["validations"] = []

        result = validate_output_llm(output_json)

        self.assertEqual(len(result["sheets"][0]["rows"]), 1000)

    def test_validate_output_llm_rejects_empty_output_object(self):
        with self.assertRaises(OutputLLMValidationError):
            validate_output_llm({})


class MapOutputCSVTest(unittest.TestCase):
    def _build_validated_output(self):
        return {
            "status": "ok",
            "summary": "valid payload",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "age", "city"],
                    "rows": [
                        {"city": "Depok", "name": "Zufar", "age": 21},
                        {"name": "Siti", "city": "Jakarta", "age": 22},
                    ],
                }
            ],
            "validations": [],
            "errors": [],
        }

    def test_mapping_output_csv_maps_single_sheet_successfully(self):
        validated_output = self._build_validated_output()

        result = map_output_csv(validated_output)

        self.assertEqual(result["sheets"][0]["name"], "Sheet1")
        self.assertEqual(result["sheets"][0]["headers"], ["name", "age", "city"])
        self.assertEqual(
            result["sheets"][0]["rows"],
            [["Zufar", 21, "Depok"], ["Siti", 22, "Jakarta"]],
        )

    def test_mapping_output_csv_maps_multiple_sheets_successfully(self):
        validated_output = self._build_validated_output()
        validated_output["sheets"].append(
            {
                "name": "Sheet2",
                "columns": ["sku", "price"],
                "rows": [{"price": 15000, "sku": "A-1"}],
            }
        )

        result = map_output_csv(validated_output)

        self.assertEqual(len(result["sheets"]), 2)
        self.assertEqual(result["sheets"][1]["headers"], ["sku", "price"])
        self.assertEqual(result["sheets"][1]["rows"], [["A-1", 15000]])

    def test_mapping_output_csv_allows_empty_rows(self):
        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["rows"] = []

        result = map_output_csv(validated_output)

        self.assertEqual(result["sheets"][0]["headers"], ["name", "age", "city"])
        self.assertEqual(result["sheets"][0]["rows"], [])

    def test_mapping_output_csv_keeps_unicode_and_formula_like_values(self):
        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["columns"] = ["name", "note"]
        validated_output["sheets"][0]["rows"] = [
            {"name": "शोफ़ी", "note": "=SUM(A1:A2)"},
        ]

        result = map_output_csv(validated_output)

        self.assertEqual(result["sheets"][0]["rows"], [["शोफ़ी", "=SUM(A1:A2)"]])

    def test_mapping_output_csv_rejects_invalid_root_or_sheets(self):
        cases = [
            ("root_non_object", "invalid"),
            ("sheets_missing", {"status": "ok"}),
            ("sheets_non_list", {"sheets": {}}),
            ("sheet_item_non_object", {"sheets": ["invalid"]}),
        ]
        for case_name, payload in cases:
            with self.subTest(case=case_name):
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(payload)

    def test_mapping_output_csv_rejects_sheet_missing_required_fields(self):
        cases = [
            ("missing_name", {"columns": ["name"], "rows": [{"name": "Zufar"}]}),
            ("missing_columns", {"name": "Sheet1", "rows": [{"name": "Zufar"}]}),
            ("missing_rows", {"name": "Sheet1", "columns": ["name"]}),
        ]
        for case_name, sheet_payload in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["sheets"] = [sheet_payload]
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(validated_output)

    def test_mapping_output_csv_rejects_invalid_columns_and_rows_container(self):
        cases = [
            ("columns_non_list", {"columns": "name"}),
            ("columns_empty", {"columns": []}),
            ("rows_non_list", {"rows": "not-list"}),
        ]
        for case_name, mutation in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["sheets"][0].update(mutation)
                with self.assertRaises(OutputCSVMappingError):
                    map_output_csv(validated_output)

    def test_mapping_output_csv_rejects_invalid_row_items_and_key_mismatch(self):
        cases = [
            ("row_non_object", ["not-dict"]),
            ("missing_column", [{"name": "Zufar", "age": 21}]),
            (
                "unknown_column",
                [{"name": "Zufar", "age": 21, "city": "Depok", "zip": 12345}],
            ),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["sheets"][0]["rows"] = rows
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
            rows.append({"name": f"user-{index}", "age": index, "city": "Depok"})

        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["rows"] = rows

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
            headers=["name", "age", "city"],
            rows=validated_output["sheets"][0]["rows"],
            sheet_index=0,
        )
        self.assertEqual(result["sheets"][0]["rows"], stubbed_rows)


class GenerateCSVTest(unittest.TestCase):
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

    def test_generate_csv_rejects_row_length_mismatch(self):
        mapped_output = self._build_mapped_output()
        mapped_output["sheets"][0]["rows"] = [["Zufar", 21]]

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


if __name__ == "__main__":
    unittest.main()
