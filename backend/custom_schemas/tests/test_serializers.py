import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import serializers

from custom_schemas.serializers import CustomSchemaSerializer


def make_definition():
    return {
        "columns": [
            {
                "name": "customer_name",
                "description": "Mapped customer field",
            }
        ]
    }


class CustomSchemaSerializerUnitTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.request = SimpleNamespace(
            user=SimpleNamespace(id=self.owner_id, is_authenticated=True)
        )

    def test_validate_definition_delegates_to_service_validator(self):
        definition = make_definition()
        serializer = CustomSchemaSerializer()

        with patch(
            "custom_schemas.serializers.validate_schema_definition"
        ) as validate_definition_mock:
            result = serializer.validate_definition(definition)

        self.assertEqual(result, definition)
        validate_definition_mock.assert_called_once_with(definition)

    def test_get_prompt_fragment_delegates_to_service_builder(self):
        serializer = CustomSchemaSerializer()
        schema = SimpleNamespace(definition=make_definition())

        with patch(
            "custom_schemas.serializers.build_schema_prompt_fragment",
            return_value="prompt fragment",
        ) as build_prompt_mock:
            result = serializer.get_prompt_fragment(schema)

        self.assertEqual(result, "prompt fragment")
        build_prompt_mock.assert_called_once_with(schema.definition)

    def test_validate_name_skips_duplicate_lookup_for_unauthenticated_user(self):
        serializer = CustomSchemaSerializer(
            context={
                "request": SimpleNamespace(
                    user=SimpleNamespace(id=None, is_authenticated=False)
                )
            }
        )
        policy_service = Mock()
        policy_service.has_name_conflict.return_value = False
        serializer.context["policy_service"] = policy_service

        result = serializer.validate_name("Invoice Mapping")

        self.assertEqual(result, "Invoice Mapping")
        policy_service.has_name_conflict.assert_called_once_with(
            user=serializer.context["request"].user,
            name="Invoice Mapping",
            exclude_pk=None,
        )

    def test_validate_name_rejects_duplicate_name_for_current_owner(self):
        policy_service = Mock()
        policy_service.has_name_conflict.return_value = True
        serializer = CustomSchemaSerializer(
            context={"request": self.request, "policy_service": policy_service}
        )

        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate_name("Invoice Mapping")

        self.assertIn(
            "Anda sudah memiliki custom schema dengan nama ini.",
            context.exception.detail,
        )
        policy_service.has_name_conflict.assert_called_once_with(
            user=self.request.user,
            name="Invoice Mapping",
            exclude_pk=None,
        )

    def test_validate_name_excludes_current_instance_from_duplicate_check(self):
        existing_instance = SimpleNamespace(pk=uuid.uuid4(), name="Invoice Mapping")
        policy_service = Mock()
        policy_service.has_name_conflict.return_value = False
        serializer = CustomSchemaSerializer(
            instance=existing_instance,
            context={"request": self.request, "policy_service": policy_service},
        )

        result = serializer.validate_name("Invoice Mapping")

        self.assertEqual(result, "Invoice Mapping")
        policy_service.has_name_conflict.assert_called_once_with(
            user=self.request.user,
            name="Invoice Mapping",
            exclude_pk=existing_instance.pk,
        )
