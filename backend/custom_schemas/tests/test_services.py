from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from custom_schemas.services import (
    CustomSchemaLimitExceededError,
    CustomSchemaPolicyService,
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
