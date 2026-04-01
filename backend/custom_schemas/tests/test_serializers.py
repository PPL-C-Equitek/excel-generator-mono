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

    def test_validate_skips_duplicate_lookup_for_unauthenticated_user(self):
        serializer = CustomSchemaSerializer(
            context={
                "request": SimpleNamespace(
                    user=SimpleNamespace(id=None, is_authenticated=False)
                )
            }
        )

        with patch("custom_schemas.serializers.CustomSchema.objects.filter") as filter_mock:
            result = serializer.validate({"name": "Invoice Mapping"})

        self.assertEqual(result, {"name": "Invoice Mapping"})
        filter_mock.assert_not_called()

    def test_validate_rejects_duplicate_name_for_current_owner(self):
        serializer = CustomSchemaSerializer(context={"request": self.request})
        duplicate_queryset = Mock()
        duplicate_queryset.exists.return_value = True

        with patch(
            "custom_schemas.serializers.CustomSchema.objects.filter",
            return_value=duplicate_queryset,
        ) as filter_mock:
            with self.assertRaises(serializers.ValidationError) as context:
                serializer.validate({"name": "Invoice Mapping"})

        self.assertIn("name", context.exception.detail)
        filter_mock.assert_called_once_with(
            owner_id=self.owner_id,
            name="Invoice Mapping",
        )
        duplicate_queryset.exists.assert_called_once_with()

    def test_validate_excludes_current_instance_from_duplicate_check(self):
        existing_instance = SimpleNamespace(pk=uuid.uuid4(), name="Invoice Mapping")
        serializer = CustomSchemaSerializer(
            instance=existing_instance,
            context={"request": self.request},
        )
        queryset = Mock()
        queryset.exclude.return_value = queryset
        queryset.exists.return_value = False

        with patch(
            "custom_schemas.serializers.CustomSchema.objects.filter",
            return_value=queryset,
        ) as filter_mock:
            result = serializer.validate({})

        self.assertEqual(result, {})
        filter_mock.assert_called_once_with(
            owner_id=self.owner_id,
            name="Invoice Mapping",
        )
        queryset.exclude.assert_called_once_with(pk=existing_instance.pk)
        queryset.exists.assert_called_once_with()
