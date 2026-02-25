from django.test import SimpleTestCase

from csv_export.services.csv_mapping_service import CSVMappingService


class CSVMappingServiceTest(SimpleTestCase):
    def test_map_rows_follows_header_order(self):
        headers = ["name", "age", "city"]
        rows = [
            {
                "city": "Depok",
                "name": "Zufar",
                "age": 21,
            }
        ]

        result = CSVMappingService().map_rows(headers=headers, rows=rows)

        self.assertEqual(result, [["Zufar", 21, "Depok"]])