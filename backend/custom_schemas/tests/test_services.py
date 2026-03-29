from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from custom_schemas.services import (
    build_schema_prompt_fragment,
    validate_schema_definition,
)


def make_definition():
    return {
        "tables": [
            {
                "table_name": "result",
                "columns": [
                    {
                        "name": "customer_name",
                        "type": "string",
                        "required": True,
                        "description": "Customer full name",
                    },
                    {
                        "name": "total_amount",
                        "type": "number",
                        "required": True,
                        "description": "Invoice total amount",
                    },
                ],
            }
        ]
    }


class CustomSchemaServiceTest(SimpleTestCase):
    def test_validate_schema_definition_accepts_valid_definition(self):
        definition = make_definition()

        validated = validate_schema_definition(definition)

        self.assertEqual(validated, definition)

    def test_validate_schema_definition_rejects_duplicate_columns(self):
        definition = make_definition()
        definition["tables"][0]["columns"].append(
            {
                "name": "customer_name",
                "type": "string",
                "required": False,
                "description": "",
            }
        )

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("duplicate column names", str(context.exception))

    def test_build_schema_prompt_fragment_lists_tables_and_columns(self):
        prompt_fragment = build_schema_prompt_fragment(make_definition())

        self.assertIn('table "result"', prompt_fragment)
        self.assertIn("customer_name (string, required)", prompt_fragment)
        self.assertIn("total_amount (number, required)", prompt_fragment)
