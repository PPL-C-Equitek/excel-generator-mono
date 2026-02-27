import unittest

from csv_export.services.validate_output_llm import (
    OutputLLMValidationError,
    ValidateOutputLLMService,
)


class ValidateOutputLLMServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ValidateOutputLLMService()

    def test_validate_output_llm_accepts_valid_ok_payload_single_sheet(self):
        output_json = {
            "status": "ok",
            "summary": "Successfully extracted 2 rows.",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "age"],
                    "rows": [{"name": "Zufar", "age": 21}, {"name": "Siti", "age": 22}],
                }
            ],
            "validations": [
                {"sheet": "Sheet1", "rule": "row_count>0", "level": "info"},
            ],
            "errors": [],
        }

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
        output_json = {
            "status": "ok",
            "summary": "Successfully extracted 2 sheets.",
            "sheets": [
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
            ],
            "validations": [],
            "errors": [],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_non_object_or_array_root(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm("not-valid")

    def test_validate_output_llm_rejects_non_object_root(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm([{"status": "ok"}])

    def test_validate_output_llm_rejects_missing_required_top_level_keys(self):
        output_json = {
            "status": "ok",
            "summary": "missing sheets, validations, errors",
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_invalid_status_value(self):
        output_json = {
            "status": "partial",
            "summary": "invalid status",
            "sheets": [],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_non_string_summary(self):
        output_json = {
            "status": "ok",
            "summary": 123,
            "sheets": [],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_sheet_missing_required_fields(self):
        output_json = {
            "status": "ok",
            "summary": "invalid sheet payload",
            "sheets": [{"name": "Sheet1", "rows": []}],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_duplicate_columns_case_insensitive(self):
        output_json = {
            "status": "ok",
            "summary": "invalid duplicate columns",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["Name", "name"],
                    "rows": [{"Name": "Zufar", "name": "Zufar"}],
                }
            ],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_row_missing_required_column(self):
        output_json = {
            "status": "ok",
            "summary": "missing required column in row",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "age"],
                    "rows": [{"name": "Zufar"}],
                }
            ],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_row_with_unknown_column(self):
        output_json = {
            "status": "ok",
            "summary": "unknown extra column in row",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "age"],
                    "rows": [{"name": "Zufar", "age": 21, "city": "Depok"}],
                }
            ],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_nested_cell_value(self):
        output_json = {
            "status": "ok",
            "summary": "nested value is invalid",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "meta"],
                    "rows": [{"name": "Zufar", "meta": {"city": "Depok"}}],
                }
            ],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_invalid_validation_level(self):
        output_json = {
            "status": "ok",
            "summary": "invalid validation level",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name"],
                    "rows": [{"name": "Zufar"}],
                }
            ],
            "validations": [
                {"sheet": "Sheet1", "rule": "must_have_name", "level": "critical"},
            ],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_non_string_error_item(self):
        output_json = {
            "status": "error",
            "summary": "error list has invalid type",
            "sheets": [],
            "validations": [],
            "errors": ["one", 2],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_blank_sheet_name(self):
        output_json = {
            "status": "ok",
            "summary": "blank sheet name",
            "sheets": [{"name": "   ", "columns": ["name"], "rows": [{"name": "Zufar"}]}],
            "validations": [],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_allows_empty_rows_per_sheet(self):
        output_json = {
            "status": "ok",
            "summary": "sheet has no rows",
            "sheets": [{"name": "Sheet1", "columns": ["name", "age"], "rows": []}],
            "validations": [],
            "errors": [],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_unicode_and_formula_like_strings(self):
        output_json = {
            "status": "ok",
            "summary": "unicode and formula-like values",
            "sheets": [
                {
                    "name": "Sheet1",
                    "columns": ["name", "note"],
                    "rows": [{"name": "शोफ़ी", "note": "=SUM(A1:A2)"}],
                }
            ],
            "validations": [],
            "errors": [],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_validation_sheet_not_found(self):
        output_json = {
            "status": "ok",
            "summary": "validation references unknown sheet",
            "sheets": [{"name": "Sheet1", "columns": ["name"], "rows": [{"name": "Zufar"}]}],
            "validations": [{"sheet": "Sheet2", "rule": "rule", "level": "warning"}],
            "errors": [],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"name": f"user-{index}", "age": index})

        output_json = {
            "status": "ok",
            "summary": "large payload",
            "sheets": [{"name": "Sheet1", "columns": ["name", "age"], "rows": rows}],
            "validations": [],
            "errors": [],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(len(result["sheets"][0]["rows"]), 1000)

    def test_validate_output_llm_rejects_empty_output_object(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm({})


if __name__ == "__main__":
    unittest.main()