from unittest.mock import Mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from authentication.models import User
from custom_schemas.services import (
    CustomSchemaApplicationService,
    CustomSchemaDefinitionService,
    CustomSchemaLimitExceededError,
    CustomSchemaPolicyService,
    DjangoCustomSchemaQueryRepository,
    build_schema_prompt_fragment,
    validate_schema_definition,
)
from custom_schemas.models import CustomSchema


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

    def test_definition_service_build_prompt_fragment_delegates_validation(self):
        service = CustomSchemaDefinitionService()
        definition = make_definition()

        prompt_fragment = service.build_prompt_fragment(definition)

        self.assertIn('single content_data table named "result"', prompt_fragment)
        self.assertIn("customer_name: Customer full name", prompt_fragment)


class CustomSchemaPolicyServiceTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = "owner-1"
        self.user = type(
            "User",
            (),
            {"id": self.owner_id, "is_authenticated": True},
        )()

    def test_get_owner_id_returns_none_for_unauthenticated_user(self):
        service = CustomSchemaPolicyService(repository=SimpleRepository())
        user = type("User", (), {"id": None, "is_authenticated": False})()

        result = service.get_owner_id(user)

        self.assertIsNone(result)

    def test_get_queryset_for_user_returns_none_queryset_when_user_missing(self):
        repository = SimpleRepository(empty_queryset="empty-queryset")
        service = CustomSchemaPolicyService(repository=repository)
        user = type("User", (), {"id": None, "is_authenticated": False})()

        result = service.get_queryset_for_user(user)

        self.assertEqual(result, "empty-queryset")

    def test_filter_queryset_by_active_applies_true_filter(self):
        repository = SimpleRepository()
        service = CustomSchemaPolicyService(repository=repository)
        queryset = DummyQueryset()

        result = service.filter_queryset_by_active(queryset, "YES")

        self.assertEqual(result, queryset.filtered_result)
        self.assertEqual(queryset.filter_kwargs, {"is_active": True})

    def test_filter_queryset_by_active_applies_false_filter(self):
        repository = SimpleRepository()
        service = CustomSchemaPolicyService(repository=repository)
        queryset = DummyQueryset()

        result = service.filter_queryset_by_active(queryset, "0")

        self.assertEqual(result, queryset.filtered_result)
        self.assertEqual(queryset.filter_kwargs, {"is_active": False})

    def test_has_name_conflict_uses_repository(self):
        repository = SimpleRepository(name_exists=True)
        service = CustomSchemaPolicyService(repository=repository)

        result = service.has_name_conflict(self.user, "Invoice Mapping", exclude_pk="schema-1")

        self.assertTrue(result)
        self.assertEqual(
            repository.name_exists_calls,
            [("owner-1", "Invoice Mapping", "schema-1")],
        )

    def test_has_name_conflict_returns_false_for_blank_name(self):
        repository = SimpleRepository(name_exists=True)
        service = CustomSchemaPolicyService(repository=repository)

        result = service.has_name_conflict(self.user, "", exclude_pk="schema-1")

        self.assertFalse(result)
        self.assertEqual(repository.name_exists_calls, [])

    def test_has_name_conflict_returns_false_when_user_has_no_owner_id(self):
        repository = SimpleRepository(name_exists=True)
        service = CustomSchemaPolicyService(repository=repository)
        unauthenticated_user = type("User", (), {"id": None, "is_authenticated": False})()

        result = service.has_name_conflict(unauthenticated_user, "Invoice Mapping")

        self.assertFalse(result)
        self.assertEqual(repository.name_exists_calls, [])

    def test_ensure_can_create_for_user_raises_when_limit_reached(self):
        repository = SimpleRepository(count=5)
        service = CustomSchemaPolicyService(repository=repository, max_custom_schemas_per_user=5)

        with self.assertRaises(CustomSchemaLimitExceededError):
            service.ensure_can_create_for_user(self.user)

    def test_ensure_can_create_for_user_returns_owner_id_when_under_limit(self):
        repository = SimpleRepository(count=4)
        service = CustomSchemaPolicyService(repository=repository, max_custom_schemas_per_user=5)

        result = service.ensure_can_create_for_user(self.user)

        self.assertEqual(result, "owner-1")

    def test_ensure_can_create_for_user_returns_none_for_missing_owner(self):
        repository = SimpleRepository(count=4)
        service = CustomSchemaPolicyService(repository=repository, max_custom_schemas_per_user=5)
        unauthenticated_user = type("User", (), {"id": None, "is_authenticated": False})()

        result = service.ensure_can_create_for_user(unauthenticated_user)

        self.assertIsNone(result)


class CustomSchemaApplicationServiceTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = "owner-1"
        self.user = type(
            "User",
            (),
            {"id": self.owner_id, "is_authenticated": True},
        )()

    def test_get_filtered_queryset_for_user_delegates_to_policy_service(self):
        policy_service = Mock()
        policy_service.get_queryset_for_user.return_value = "base-queryset"
        policy_service.filter_queryset_by_active.return_value = "filtered-queryset"
        service = CustomSchemaApplicationService(policy_service=policy_service)

        result = service.get_filtered_queryset_for_user(self.user, "true")

        self.assertEqual(result, "filtered-queryset")
        policy_service.get_queryset_for_user.assert_called_once_with(self.user)
        policy_service.filter_queryset_by_active.assert_called_once_with(
            queryset="base-queryset",
            active_value="true",
        )

    def test_has_name_conflict_delegates_to_policy_service(self):
        policy_service = Mock()
        policy_service.has_name_conflict.return_value = True
        service = CustomSchemaApplicationService(policy_service=policy_service)

        result = service.has_name_conflict(
            self.user,
            "Invoice Mapping",
            exclude_pk="schema-1",
        )

        self.assertTrue(result)
        policy_service.has_name_conflict.assert_called_once_with(
            user=self.user,
            name="Invoice Mapping",
            exclude_pk="schema-1",
        )

    def test_get_limit_exceeded_message_uses_policy_limit(self):
        policy_service = Mock()
        policy_service.max_custom_schemas_per_user = 7
        service = CustomSchemaApplicationService(policy_service=policy_service)

        result = service.get_limit_exceeded_message()

        self.assertEqual(result, "A user can only have up to 7 custom schemas.")


class DjangoCustomSchemaQueryRepositoryTest(TestCase):
    def setUp(self):
        self.repository = DjangoCustomSchemaQueryRepository()
        self.owner = User.objects.create_user(
            email="repository-owner@example.com",
            name="Repository Owner",
            password="Test12345",
            status="verified",
        )

    def test_none_returns_empty_queryset(self):
        result = self.repository.none()

        self.assertEqual(result.count(), 0)

    def test_name_exists_for_owner_excludes_current_schema_when_requested(self):
        schema = CustomSchema.objects.create(
            owner=self.owner,
            name="Invoice Mapping",
            definition=make_definition(),
        )

        result = self.repository.name_exists_for_owner(
            owner_id=self.owner.id,
            name="Invoice Mapping",
            exclude_pk=schema.pk,
        )

        self.assertFalse(result)


class DummyQueryset:
    def __init__(self):
        self.filter_kwargs = None
        self.filtered_result = "filtered-queryset"

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self.filtered_result


class SimpleRepository:
    def __init__(self, empty_queryset=None, count=0, name_exists=False):
        self.empty_queryset = empty_queryset or "empty"
        self.count = count
        self.name_exists = name_exists
        self.name_exists_calls = []

    def none(self):
        return self.empty_queryset

    def for_owner(self, owner_id):
        return f"queryset-for-{owner_id}"

    def count_for_owner(self, owner_id):
        return self.count

    def name_exists_for_owner(self, owner_id, name, exclude_pk=None):
        self.name_exists_calls.append((owner_id, name, exclude_pk))
        return self.name_exists
