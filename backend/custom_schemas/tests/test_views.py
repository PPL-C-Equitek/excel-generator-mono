from django.test import TestCase
from rest_framework.test import APIRequestFactory

from custom_schemas.models import CustomSchema
from custom_schemas.views import CustomSchemaDetailView, CustomSchemaListCreateView


def make_definition(column_name="customer_name"):
    return {
        "columns": [
            {
                "name": column_name,
                "description": "Mapped customer field",
            }
        ]
    }


class CustomSchemaApiViewTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_create_schema_returns_created_resource(self):
        request = self.factory.post(
            "/schemas/",
            {
                "name": "Invoice Mapping",
                "description": "Maps invoice data into a flat table",
                "definition": make_definition(),
            },
            format="json",
        )

        response = CustomSchemaListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Invoice Mapping")
        self.assertEqual(response.data["version"], 1)
        self.assertIn("prompt_fragment", response.data)
        self.assertEqual(CustomSchema.objects.count(), 1)

    def test_list_schema_can_filter_active_items(self):
        active_schema = CustomSchema.objects.create(
            name="Active Schema",
            definition=make_definition("active_column"),
        )
        CustomSchema.objects.create(
            name="Inactive Schema",
            is_active=False,
            definition=make_definition("inactive_column"),
        )

        request = self.factory.get("/schemas/?active=true")

        response = CustomSchemaListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], active_schema.id)

    def test_update_definition_increments_schema_version(self):
        schema = CustomSchema.objects.create(
            name="Receipt Mapping",
            definition=make_definition("receipt_number"),
        )

        request = self.factory.patch(
            f"/schemas/{schema.id}/",
            {"definition": make_definition("receipt_code")},
            format="json",
        )

        response = CustomSchemaDetailView.as_view()(request, pk=schema.id)
        schema.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], 2)
        self.assertEqual(schema.version, 2)

    def test_delete_schema_returns_no_content(self):
        schema = CustomSchema.objects.create(
            name="Temporary Mapping",
            definition=make_definition("temporary_column"),
        )

        request = self.factory.delete(f"/schemas/{schema.id}/")

        response = CustomSchemaDetailView.as_view()(request, pk=schema.id)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(CustomSchema.objects.filter(pk=schema.id).exists())
