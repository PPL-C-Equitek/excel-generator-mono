import unittest
from copy import deepcopy

from file_processing.services.csv_mapping import (
    MappingOutputCSVService,
    OutputCSVMappingError,
)


class MappingOutputCSVServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = MappingOutputCSVService()

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

        result = self.service.map_output_csv(validated_output)

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

        result = self.service.map_output_csv(validated_output)

        self.assertEqual(len(result["sheets"]), 2)
        self.assertEqual(result["sheets"][1]["headers"], ["sku", "price"])
        self.assertEqual(result["sheets"][1]["rows"], [["A-1", 15000]])

    def test_mapping_output_csv_allows_empty_rows(self):
        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["rows"] = []

        result = self.service.map_output_csv(validated_output)

        self.assertEqual(result["sheets"][0]["headers"], ["name", "age", "city"])
        self.assertEqual(result["sheets"][0]["rows"], [])

    def test_mapping_output_csv_keeps_unicode_and_formula_like_values(self):
        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["columns"] = ["name", "note"]
        validated_output["sheets"][0]["rows"] = [
            {"name": "शोफ़ी", "note": "=SUM(A1:A2)"},
        ]

        result = self.service.map_output_csv(validated_output)

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
                    self.service.map_output_csv(payload)

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
                    self.service.map_output_csv(validated_output)

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
                    self.service.map_output_csv(validated_output)

    def test_mapping_output_csv_rejects_invalid_row_items_and_key_mismatch(self):
        cases = [
            ("row_non_object", ["not-dict"]),
            ("missing_column", [{"name": "Zufar", "age": 21}]),
            ("unknown_column", [{"name": "Zufar", "age": 21, "city": "Depok", "zip": 12345}]),
        ]
        for case_name, rows in cases:
            with self.subTest(case=case_name):
                validated_output = self._build_validated_output()
                validated_output["sheets"][0]["rows"] = rows
                with self.assertRaises(OutputCSVMappingError):
                    self.service.map_output_csv(validated_output)

    def test_mapping_output_csv_does_not_mutate_input_payload(self):
        validated_output = self._build_validated_output()
        original = deepcopy(validated_output)

        _ = self.service.map_output_csv(validated_output)

        self.assertEqual(validated_output, original)

    def test_mapping_output_csv_handles_large_payload_smoke(self):
        rows = []
        for index in range(1000):
            rows.append({"name": f"user-{index}", "age": index, "city": "Depok"})

        validated_output = self._build_validated_output()
        validated_output["sheets"][0]["rows"] = rows

        result = self.service.map_output_csv(validated_output)

        self.assertEqual(len(result["sheets"][0]["rows"]), 1000)


if __name__ == "__main__":
    unittest.main()