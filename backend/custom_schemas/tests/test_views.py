from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from types import SimpleNamespace
import uuid

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
        self.list_view = CustomSchemaListCreateView.as_view()
        self.detail_view = CustomSchemaDetailView.as_view()
        self.user = SimpleNamespace(
            id=uuid.uuid4(),
            email="owner@example.com",
            is_authenticated=True,
        )
        self.other_user = SimpleNamespace(
            id=uuid.uuid4(),
            email="other@example.com",
            is_authenticated=True,
        )

    def test_create_schema_returns_created_resource_for_authenticated_user(self):
        request = self.factory.post(
            "/schemas/",
            {
                "name": "Invoice Mapping",
                "description": "Maps invoice data into a flat table",
                "definition": make_definition(),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], str(CustomSchema.objects.get().id))
        self.assertEqual(response.data["name"], "Invoice Mapping")
        self.assertEqual(response.data["owner_id"], str(self.user.id))
        self.assertIn("prompt_fragment", response.data)

        created_schema = CustomSchema.objects.get()
        self.assertEqual(created_schema.owner_id, self.user.id)

    def test_create_schema_requires_authentication(self):
        request = self.factory.post(
            "/schemas/",
            {
                "name": "Invoice Mapping",
                "description": "Maps invoice data into a flat table",
                "definition": make_definition(),
            },
            format="json",
        )

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(CustomSchema.objects.count(), 0)

    def test_list_schemas_returns_only_current_users_items(self):
        owned_schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Owned Schema",
            definition=make_definition("owned_column"),
        )
        other_owned_schema = CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Other User Schema",
            definition=make_definition("other_column"),
        )

        request = self.factory.get("/schemas/")
        force_authenticate(request, user=self.user)

        response = self.list_view(request)
        returned_ids = {item["id"] for item in response.data}

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(returned_ids, {str(owned_schema.id)})
        self.assertNotIn(str(other_owned_schema.id), returned_ids)

    def test_list_schema_can_filter_active_items_for_current_user(self):
        active_schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Active Schema",
            definition=make_definition("active_column"),
        )
        CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Inactive Schema",
            is_active=False,
            definition=make_definition("inactive_column"),
        )
        CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Other User Active Schema",
            definition=make_definition("other_active_column"),
        )

        request = self.factory.get("/schemas/?active=true")
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(active_schema.id))

    def test_list_schema_with_invalid_active_param_returns_all_current_users_items(self):
        active_schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Visible Active Schema",
            definition=make_definition("visible_active_column"),
        )
        inactive_schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Visible Inactive Schema",
            is_active=False,
            definition=make_definition("visible_inactive_column"),
        )
        CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Other User Schema",
            definition=make_definition("other_visible_column"),
        )

        request = self.factory.get("/schemas/?active=maybe")
        force_authenticate(request, user=self.user)

        response = self.list_view(request)
        returned_ids = {item["id"] for item in response.data}

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(returned_ids, {str(active_schema.id), str(inactive_schema.id)})

    def test_owner_can_update_definition(self):
        schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Receipt Mapping",
            definition=make_definition("receipt_number"),
        )

        request = self.factory.patch(
            f"/schemas/{schema.id}/",
            {"definition": make_definition("receipt_code")},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = self.detail_view(request, pk=schema.id)
        schema.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["definition"],
            make_definition("receipt_code"),
        )
        self.assertEqual(schema.definition, make_definition("receipt_code"))

    def test_user_cannot_retrieve_another_users_schema(self):
        schema = CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Private Mapping",
            definition=make_definition("private_column"),
        )

        request = self.factory.get(f"/schemas/{schema.id}/")
        force_authenticate(request, user=self.user)

        response = self.detail_view(request, pk=schema.id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_update_another_users_schema(self):
        schema = CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Private Mapping",
            definition=make_definition("private_column"),
        )

        request = self.factory.patch(
            f"/schemas/{schema.id}/",
            {"description": "Updated by attacker"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = self.detail_view(request, pk=schema.id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_schema_returns_no_content_for_owner(self):
        schema = CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Temporary Mapping",
            definition=make_definition("temporary_column"),
        )

        request = self.factory.delete(f"/schemas/{schema.id}/")
        force_authenticate(request, user=self.user)

        response = self.detail_view(request, pk=schema.id)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CustomSchema.objects.filter(pk=schema.id).exists())

    def test_user_cannot_delete_another_users_schema(self):
        schema = CustomSchema.objects.create(
            owner_id=self.other_user.id,
            name="Other User Temporary Mapping",
            definition=make_definition("other_temporary_column"),
        )

        request = self.factory.delete(f"/schemas/{schema.id}/")
        force_authenticate(request, user=self.user)

        response = self.detail_view(request, pk=schema.id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(CustomSchema.objects.filter(pk=schema.id).exists())

    def test_create_schema_rejects_sixth_schema_for_same_user(self):
        for index in range(5):
            CustomSchema.objects.create(
                owner_id=self.user.id,
                name=f"Schema {index + 1}",
                definition=make_definition(f"column_{index + 1}"),
            )

        request = self.factory.post(
            "/schemas/",
            {
                "name": "Schema 6",
                "description": "This should fail",
                "definition": make_definition("column_6"),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.data)
        self.assertEqual(CustomSchema.objects.filter(owner_id=self.user.id).count(), 5)

    def test_same_schema_name_is_allowed_for_different_users(self):
        request = self.factory.post(
            "/schemas/",
            {
                "name": "Shared Mapping",
                "description": "First owner's schema",
                "definition": make_definition("first_column"),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        first_response = self.list_view(request)

        second_request = self.factory.post(
            "/schemas/",
            {
                "name": "Shared Mapping",
                "description": "Second owner's schema",
                "definition": make_definition("second_column"),
            },
            format="json",
        )
        force_authenticate(second_request, user=self.other_user)
        second_response = self.list_view(second_request)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            CustomSchema.objects.filter(name="Shared Mapping").count(),
            2,
        )

    def test_duplicate_schema_name_for_same_user_returns_400(self):
        CustomSchema.objects.create(
            owner_id=self.user.id,
            name="Duplicate Mapping",
            definition=make_definition("first_column"),
        )

        request = self.factory.post(
            "/schemas/",
            {
                "name": "Duplicate Mapping",
                "description": "This should fail",
                "definition": make_definition("second_column"),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = self.list_view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
