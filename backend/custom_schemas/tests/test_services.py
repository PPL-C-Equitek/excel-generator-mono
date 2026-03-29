from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from custom_schemas.services import (
    build_schema_prompt_fragment,
    validate_schema_definition,
)


def make_definition():
    return {
        "columns": [
            {
                "name": "customer_name",
                "description": "Customer full name",
            },
            {
                "name": "total_amount",
                "description": "Invoice total amount",
            },
        ]
    }


class CustomSchemaServiceTest(SimpleTestCase):
    def test_validate_schema_definition_accepts_valid_definition(self):
        definition = make_definition()

        validated = validate_schema_definition(definition)

        self.assertEqual(validated, definition)

    def test_validate_schema_definition_rejects_duplicate_columns(self):
        definition = make_definition()
        definition["columns"].append(
            {
                "name": "customer_name",
                "description": "",
            }
        )

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("duplicate names", str(context.exception))

    def test_build_schema_prompt_fragment_lists_tables_and_columns(self):
        prompt_fragment = build_schema_prompt_fragment(make_definition())

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("customer_name: Customer full name", prompt_fragment)
        self.assertIn("total_amount: Invoice total amount", prompt_fragment)

    def test_validate_schema_definition_rejects_missing_description(self):
        definition = {"columns": [{"name": "customer_name"}]}

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("description is required", str(context.exception))
