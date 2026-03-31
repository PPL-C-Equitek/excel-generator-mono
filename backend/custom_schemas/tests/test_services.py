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
    def test_validate_schema_definition_rejects_non_object_root(self):
        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(["not-an-object"])

        self.assertIn("JSON object", str(context.exception))

    def test_validate_schema_definition_rejects_missing_or_empty_columns_list(self):
        with self.assertRaises(ValidationError) as missing_context:
            validate_schema_definition({})

        with self.assertRaises(ValidationError) as empty_context:
            validate_schema_definition({"columns": []})

        self.assertIn("non-empty 'columns' list", str(missing_context.exception))
        self.assertIn("non-empty 'columns' list", str(empty_context.exception))

    def test_validate_schema_definition_accepts_valid_definition(self):
        definition = make_definition()

        validated = validate_schema_definition(definition)

        self.assertEqual(validated, definition)

    def test_validate_schema_definition_rejects_non_object_column_entry(self):
        definition = {"columns": ["not-an-object"]}

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("columns[0] must be an object", str(context.exception))

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

    def test_validate_schema_definition_rejects_blank_column_name(self):
        definition = {"columns": [{"name": "   ", "description": "Blank header"}]}

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("name must be a non-empty string", str(context.exception))

    def test_validate_schema_definition_rejects_non_string_description(self):
        definition = {"columns": [{"name": "customer_name", "description": 123}]}

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("description must be a string", str(context.exception))

    def test_build_schema_prompt_fragment_lists_tables_and_columns(self):
        prompt_fragment = build_schema_prompt_fragment(make_definition())

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("customer_name: Customer full name", prompt_fragment)
        self.assertIn("total_amount: Invoice total amount", prompt_fragment)

    def test_build_schema_prompt_fragment_omits_colon_for_blank_description(self):
        prompt_fragment = build_schema_prompt_fragment(
            {"columns": [{"name": "customer_name", "description": "   "}]}
        )

        self.assertIn("  - customer_name", prompt_fragment)
        self.assertNotIn("customer_name:", prompt_fragment)

    def test_validate_schema_definition_rejects_missing_description(self):
        definition = {"columns": [{"name": "customer_name"}]}

        with self.assertRaises(ValidationError) as context:
            validate_schema_definition(definition)

        self.assertIn("description is required", str(context.exception))
