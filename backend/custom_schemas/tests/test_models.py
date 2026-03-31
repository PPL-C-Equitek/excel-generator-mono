from django.core.exceptions import ValidationError
from django.test import TestCase

from custom_schemas.models import CustomSchema


def make_definition(column_name="customer_name", description="Mapped customer field"):
    return {
        "columns": [
            {
                "name": column_name,
                "description": description,
            }
        ]
    }


class CustomSchemaModelTest(TestCase):
    def test_str_returns_name_and_version(self):
        schema = CustomSchema(
            name="Invoice Mapping",
            version=3,
            definition=make_definition(),
        )

        self.assertEqual(str(schema), "Invoice Mapping (v3)")

    def test_prompt_fragment_uses_definition(self):
        schema = CustomSchema(
            name="Invoice Mapping",
            definition=make_definition("invoice_number", "Invoice identifier"),
        )

        prompt_fragment = schema.prompt_fragment

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("invoice_number: Invoice identifier", prompt_fragment)

    def test_clean_rejects_version_lower_than_one(self):
        schema = CustomSchema(
            name="Invalid Version Schema",
            version=0,
            definition=make_definition(),
        )

        with self.assertRaises(ValidationError) as context:
            schema.clean()

        self.assertIn("Version must be at least 1", str(context.exception))

    def test_save_increments_version_when_definition_changes(self):
        schema = CustomSchema.objects.create(
            name="Receipt Mapping",
            definition=make_definition("receipt_number", "Receipt number"),
        )

        schema.definition = make_definition("receipt_code", "Receipt code")
        schema.save()
        schema.refresh_from_db()

        self.assertEqual(schema.version, 2)
