from django.core.exceptions import ValidationError
from django.test import TestCase
import uuid

from authentication.models import User
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
        self.owner = User.objects.create_user(
            email="owner@example.com",
            name="Owner",
            password="Test12345",
            status="verified",
        )
        self.other_owner = User.objects.create_user(
            email="other-owner@example.com",
            name="Other Owner",
            password="Test12345",
            status="verified",
        )

    def test_str_returns_name(self):
        schema = CustomSchema(
            owner=self.owner,
            name="Invoice Mapping",
            definition=make_definition(),
        )

        self.assertEqual(str(schema), "Invoice Mapping")

    def test_primary_key_defaults_to_uuid(self):
        schema = CustomSchema.objects.create(
            owner=self.owner,
            name="UUID Mapping",
            definition=make_definition(),
        )

        self.assertIsInstance(schema.id, uuid.UUID)

    def test_prompt_fragment_uses_definition(self):
        schema = CustomSchema(
            owner=self.owner,
            name="Invoice Mapping",
            definition=make_definition("invoice_number", "Invoice identifier"),
        )

        prompt_fragment = schema.prompt_fragment

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("invoice_number: Invoice identifier", prompt_fragment)

    def test_save_persists_definition_changes_without_versioning(self):
        schema = CustomSchema.objects.create(
            owner=self.owner,
            name="Receipt Mapping",
            definition=make_definition("receipt_number", "Receipt number"),
        )

        schema.definition = make_definition("receipt_code", "Receipt code")
        schema.save()
        schema.refresh_from_db()

        self.assertEqual(
            schema.definition,
            make_definition("receipt_code", "Receipt code"),
        )

    def test_same_name_is_allowed_for_different_users(self):
        CustomSchema.objects.create(
            owner=self.owner,
            name="Shared Name",
            definition=make_definition("owner_column", "Owner column"),
        )

        schema = CustomSchema.objects.create(
            owner=self.other_owner,
            name="Shared Name",
            definition=make_definition("other_column", "Other owner column"),
        )

        self.assertEqual(schema.name, "Shared Name")

    def test_duplicate_name_for_same_user_is_rejected(self):
        CustomSchema.objects.create(
            owner=self.owner,
            name="Duplicate Name",
            definition=make_definition("first_column", "First column"),
        )

        duplicate_schema = CustomSchema(
            owner=self.owner,
            name="Duplicate Name",
            definition=make_definition("second_column", "Second column"),
        )

        with self.assertRaises(ValidationError) as context:
            duplicate_schema.save()

        self.assertIn("name", str(context.exception).lower())
