from django.core.exceptions import ValidationError
from django.test import TestCase
import uuid

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
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.other_owner_id = uuid.uuid4()

    def test_str_returns_name_and_version(self):
        schema = CustomSchema(
            owner_id=self.owner_id,
            name="Invoice Mapping",
            version=3,
            definition=make_definition(),
        )

        self.assertEqual(str(schema), "Invoice Mapping (v3)")

    def test_prompt_fragment_uses_definition(self):
        schema = CustomSchema(
            owner_id=self.owner_id,
            name="Invoice Mapping",
            definition=make_definition("invoice_number", "Invoice identifier"),
        )

        prompt_fragment = schema.prompt_fragment

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("invoice_number: Invoice identifier", prompt_fragment)

    def test_clean_rejects_version_lower_than_one(self):
        schema = CustomSchema(
            owner_id=self.owner_id,
            name="Invalid Version Schema",
            version=0,
            definition=make_definition(),
        )

        with self.assertRaises(ValidationError) as context:
            schema.clean()

        self.assertIn("Version must be at least 1", str(context.exception))

    def test_save_increments_version_when_definition_changes(self):
        schema = CustomSchema.objects.create(
            owner_id=self.owner_id,
            name="Receipt Mapping",
            definition=make_definition("receipt_number", "Receipt number"),
        )

        schema.definition = make_definition("receipt_code", "Receipt code")
        schema.save()
        schema.refresh_from_db()

        self.assertEqual(schema.version, 2)

    def test_save_keeps_version_when_definition_does_not_change(self):
        schema = CustomSchema.objects.create(
            owner_id=self.owner_id,
            name="Stable Mapping",
            definition=make_definition("stable_column", "Stable description"),
        )

        schema.description = "Updated metadata only"
        schema.save()
        schema.refresh_from_db()

        self.assertEqual(schema.version, 1)

    def test_same_name_is_allowed_for_different_users(self):
        CustomSchema.objects.create(
            owner_id=self.owner_id,
            name="Shared Name",
            definition=make_definition("owner_column", "Owner column"),
        )

        schema = CustomSchema.objects.create(
            owner_id=self.other_owner_id,
            name="Shared Name",
            definition=make_definition("other_column", "Other owner column"),
        )

        self.assertEqual(schema.name, "Shared Name")

    def test_duplicate_name_for_same_user_is_rejected(self):
        CustomSchema.objects.create(
            owner_id=self.owner_id,
            name="Duplicate Name",
            definition=make_definition("first_column", "First column"),
        )

        duplicate_schema = CustomSchema(
            owner_id=self.owner_id,
            name="Duplicate Name",
            definition=make_definition("second_column", "Second column"),
        )

        with self.assertRaises(ValidationError) as context:
            duplicate_schema.save()

        self.assertIn("name", str(context.exception).lower())
