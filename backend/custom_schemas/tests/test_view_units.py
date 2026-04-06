import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from custom_schemas.views import (
    MAX_CUSTOM_SCHEMAS_PER_USER,
    CustomSchemaDetailView,
    CustomSchemaListCreateView,
)


class CustomSchemaViewUnitTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.user = SimpleNamespace(id=self.owner_id, is_authenticated=True)

    def test_get_base_queryset_returns_none_for_unauthenticated_user(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(
            user=SimpleNamespace(id=None, is_authenticated=False)
        )

        with patch(
            "custom_schemas.views.CustomSchema.objects.none",
            return_value="empty-queryset",
        ) as none_mock:
            with patch("custom_schemas.views.CustomSchema.objects.filter") as filter_mock:
                result = view.get_base_queryset()

        self.assertEqual(result, "empty-queryset")
        none_mock.assert_called_once_with()
        filter_mock.assert_not_called()

    def test_get_base_queryset_filters_by_current_owner_id(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(user=self.user)

        with patch(
            "custom_schemas.views.CustomSchema.objects.filter",
            return_value="owner-queryset",
        ) as filter_mock:
            result = view.get_base_queryset()

        self.assertEqual(result, "owner-queryset")
        filter_mock.assert_called_once_with(owner_id=self.owner_id)

    def test_list_view_filters_active_true_values(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        base_queryset.filter.return_value = "active-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "YES"})
        view.get_base_queryset = Mock(return_value=base_queryset)

        result = view.get_queryset()

        self.assertEqual(result, "active-queryset")
        view.get_base_queryset.assert_called_once_with()
        base_queryset.filter.assert_called_once_with(is_active=True)

    def test_list_view_filters_active_false_values(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        base_queryset.filter.return_value = "inactive-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "0"})
        view.get_base_queryset = Mock(return_value=base_queryset)

        result = view.get_queryset()

        self.assertEqual(result, "inactive-queryset")
        base_queryset.filter.assert_called_once_with(is_active=False)

    def test_list_view_ignores_invalid_active_value(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        view.request = SimpleNamespace(user=self.user, query_params={"active": "maybe"})
        view.get_base_queryset = Mock(return_value=base_queryset)

        result = view.get_queryset()

        self.assertIs(result, base_queryset)
        base_queryset.filter.assert_not_called()

    def test_perform_create_saves_owner_id_when_user_is_under_limit(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        base_queryset = Mock()
        base_queryset.count.return_value = MAX_CUSTOM_SCHEMAS_PER_USER - 1
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.get_base_queryset = Mock(return_value=base_queryset)

        view.perform_create(serializer)

        serializer.save.assert_called_once_with(owner_id=self.owner_id)

    def test_perform_create_rejects_sixth_schema_and_does_not_save(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        base_queryset = Mock()
        base_queryset.count.return_value = MAX_CUSTOM_SCHEMAS_PER_USER
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.get_base_queryset = Mock(return_value=base_queryset)

        with self.assertRaises(ValidationError) as context:
            view.perform_create(serializer)

        self.assertIn("message", context.exception.detail)
        serializer.save.assert_not_called()

    def test_detail_view_uses_user_scoped_queryset(self):
        view = CustomSchemaDetailView()
        base_queryset = Mock()
        view.get_base_queryset = Mock(return_value=base_queryset)

        result = view.get_queryset()

        self.assertIs(result, base_queryset)
        view.get_base_queryset.assert_called_once_with()
