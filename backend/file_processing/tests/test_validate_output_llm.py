import unittest
from copy import deepcopy

from file_processing.services.validate_output_llm import (
    OutputLLMValidationError,
    ValidateOutputLLMService,
)


class ValidateOutputLLMServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ValidateOutputLLMService()

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

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_valid_error_payload(self):
        output_json = {
            "status": "error",
            "summary": "Extraction failed for uploaded file.",
            "sheets": [],
            "validations": [],
            "errors": ["Unsupported file structure"],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_valid_multiple_sheets_payload(self):
        output_json = self._build_valid_payload()
        output_json["sheets"] = [
            {"name": "Employees", "columns": ["name", "age"], "rows": [{"name": "Zufar", "age": 21}]},
            {"name": "Products", "columns": ["sku", "price"], "rows": [{"sku": "A-1", "price": 15000}]},
        ]
        output_json["validations"] = [{"sheet": "Employees", "rule": "row_count>0", "level": "warning"}]

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_non_object_or_array_root(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm("not-valid")

    def test_validate_output_llm_rejects_missing_required_top_level_keys(self):
        required_keys = ("status", "summary", "sheets", "validations", "errors")
        for key in required_keys:
            with self.subTest(missing_key=key):
                payload = self._build_valid_payload()
                payload.pop(key)
                with self.assertRaises(OutputLLMValidationError):
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_sheet_structure(self):
        cases = [
            ("sheet_non_object", ["x"]),
            ("missing_name", [{"columns": ["name"], "rows": [{"name": "Zufar"}]}]),
            ("missing_columns", [{"name": "Sheet1", "rows": [{"name": "Zufar"}]}]),
            ("missing_rows", [{"name": "Sheet1", "columns": ["name"]}]),
            ("sheet_name_non_string", [{"name": 123, "columns": ["name"], "rows": [{"name": "Zufar"}]}]),
            ("sheet_name_blank", [{"name": "   ", "columns": ["name"], "rows": [{"name": "Zufar"}]}]),
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
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

    def test_validate_output_llm_rejects_invalid_validation_fields(self):
        cases = [
            ("validation_sheet_non_string", [{"sheet": 1, "rule": "r", "level": "info"}]),
            ("validation_sheet_blank", [{"sheet": "  ", "rule": "r", "level": "info"}]),
            ("validation_sheet_unknown", [{"sheet": "Unknown", "rule": "r", "level": "info"}]),
            ("validation_rule_non_string", [{"sheet": "Sheet1", "rule": 1, "level": "info"}]),
            ("validation_rule_blank", [{"sheet": "Sheet1", "rule": " ", "level": "info"}]),
            ("validation_level_non_string", [{"sheet": "Sheet1", "rule": "r", "level": 1}]),
            ("validation_level_not_allowed", [{"sheet": "Sheet1", "rule": "r", "level": "critical"}]),
        ]
        for case_name, validations in cases:
            with self.subTest(case=case_name):
                payload = self._build_valid_payload()
                payload["validations"] = validations
                with self.assertRaises(OutputLLMValidationError):
                    self.service.validate_output_llm(payload)

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
                    self.service.validate_output_llm(payload)

    def test_validate_output_llm_allows_empty_rows_per_sheet(self):
        output_json = self._build_valid_payload()
        output_json["sheets"][0]["rows"] = []

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_unicode_and_formula_like_strings(self):
        output_json = self._build_valid_payload()
        output_json["sheets"][0] = {
            "name": "Sheet1",
            "columns": ["name", "note"],
            "rows": [{"name": "शोफ़ी", "note": "=SUM(A1:A2)"}],
        }
        output_json["validations"] = []

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"name": f"user-{index}", "age": index})

        output_json = self._build_valid_payload()
        output_json["sheets"][0]["rows"] = rows
        output_json["validations"] = []

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(len(result["sheets"][0]["rows"]), 1000)

    def test_validate_output_llm_rejects_empty_output_object(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm({})


if __name__ == "__main__":
    unittest.main()
