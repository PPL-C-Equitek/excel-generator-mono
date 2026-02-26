import unittest

from csv_export.services.validate_output_llm import (
    OutputLLMValidationError,
    ValidateOutputLLMService,
)


class ValidateOutputLLMServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = ValidateOutputLLMService()

    def test_validate_output_llm_accepts_object_schema_headers_rows(self):
        output_json = {
            "headers": ["name", "age"],
            "rows": [{"name": "Zufar", "age": 21}, {"name": "Siti", "age": 22}],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_array_schema_and_infers_headers(self):
        output_json = [{"name": "Zufar", "age": 21}, {"name": "Siti", "age": 22}]

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result["headers"], ["name", "age"])
        self.assertEqual(result["rows"], output_json)

    def test_validate_output_llm_accepts_empty_rows_with_explicit_headers(self):
        output_json = {"headers": ["name", "age"], "rows": []}

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_accepts_scalar_cell_types(self):
        output_json = {
            "headers": ["s", "i", "f", "b", "n"],
            "rows": [{"s": "x", "i": 1, "f": 1.25, "b": True, "n": None}],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_rejects_non_object_or_array_root(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm("not-valid")

    def test_validate_output_llm_rejects_prompt_drift_unknown_top_level_keys(self):
        output_json = {"message": "done", "analysis": "ok"}

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_missing_headers_in_object_schema(self):
        output_json = {"rows": [{"name": "Zufar"}]}

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_missing_rows_in_object_schema(self):
        output_json = {"headers": ["name"]}

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_duplicate_headers_case_insensitive(self):
        output_json = {
            "headers": ["Name", "name"],
            "rows": [{"Name": "Zufar", "name": "Zufar"}],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_row_missing_required_header(self):
        output_json = {"headers": ["name", "age"], "rows": [{"name": "Zufar"}]}

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_non_object_row(self):
        output_json = {"headers": ["name"], "rows": ["Zufar"]}

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_nested_cell_value(self):
        output_json = {
            "headers": ["name", "meta"],
            "rows": [{"name": "Zufar", "meta": {"city": "Depok"}}],
        }

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_inconsistent_row_keys_across_rows(self):
        output_json = [{"name": "Zufar", "age": 21}, {"name": "Siti", "city": "Depok"}]

        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm(output_json)

    def test_validate_output_llm_rejects_empty_array_without_header_context(self):
        with self.assertRaises(OutputLLMValidationError):
            self.service.validate_output_llm([])

    def test_validate_output_llm_handles_random_row_key_order_consistently(self):
        output_json = [
            {"age": 21, "name": "Zufar"},
            {"name": "Siti", "age": 22},
        ]

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result["headers"], ["age", "name"])
        self.assertEqual(result["rows"], output_json)

    def test_validate_output_llm_accepts_unicode_and_formula_like_strings(self):
        output_json = {
            "headers": ["name", "note"],
            "rows": [{"name": "शोफ़ी", "note": "=SUM(A1:A2)"}],
        }

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(result, output_json)

    def test_validate_output_llm_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"name": f"user-{index}", "age": index})

        output_json = {"headers": ["name", "age"], "rows": rows}

        result = self.service.validate_output_llm(output_json)

        self.assertEqual(len(result["rows"]), 1000)


if __name__ == "__main__":
    unittest.main()
