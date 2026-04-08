import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from custom_schemas.services import CustomSchemaLimitExceededError
from custom_schemas.views import (
    MAX_CUSTOM_SCHEMAS_PER_USER,
    CustomSchemaDetailView,
    CustomSchemaListCreateView,
)


class CustomSchemaViewUnitTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.user = SimpleNamespace(id=self.owner_id, is_authenticated=True)

    def test_get_current_user_id_delegates_to_policy_service(self):
        view = CustomSchemaListCreateView()
        policy_service = Mock()
        policy_service.get_owner_id.return_value = self.owner_id
        view.request = SimpleNamespace(user=self.user)
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_current_user_id()

        self.assertEqual(result, self.owner_id)
        policy_service.get_owner_id.assert_called_once_with(self.user)

    def test_get_base_queryset_returns_none_for_unauthenticated_user(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(
            user=SimpleNamespace(id=None, is_authenticated=False)
        )
        policy_service = Mock()
        policy_service.get_queryset_for_user.return_value = "empty-queryset"
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_base_queryset()

        self.assertEqual(result, "empty-queryset")
        policy_service.get_queryset_for_user.assert_called_once_with(view.request.user)

    def test_get_base_queryset_filters_by_current_owner_id(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(user=self.user)
        policy_service = Mock()
        policy_service.get_queryset_for_user.return_value = "owner-queryset"
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_base_queryset()

        self.assertEqual(result, "owner-queryset")
        policy_service.get_queryset_for_user.assert_called_once_with(self.user)

    def test_list_view_filters_active_true_values(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        policy_service = Mock()
        policy_service.filter_queryset_by_active.return_value = "active-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "YES"})
        view.get_base_queryset = Mock(return_value=base_queryset)
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_queryset()

        self.assertEqual(result, "active-queryset")
        view.get_base_queryset.assert_called_once_with()
        policy_service.filter_queryset_by_active.assert_called_once_with(
            queryset=base_queryset,
            active_value="YES",
        )

    def test_list_view_filters_active_false_values(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        policy_service = Mock()
        policy_service.filter_queryset_by_active.return_value = "inactive-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "0"})
        view.get_base_queryset = Mock(return_value=base_queryset)
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_queryset()

        self.assertEqual(result, "inactive-queryset")
        policy_service.filter_queryset_by_active.assert_called_once_with(
            queryset=base_queryset,
            active_value="0",
        )

    def test_list_view_ignores_invalid_active_value(self):
        view = CustomSchemaListCreateView()
        base_queryset = Mock()
        policy_service = Mock()
        policy_service.filter_queryset_by_active.return_value = base_queryset
        view.request = SimpleNamespace(user=self.user, query_params={"active": "maybe"})
        view.get_base_queryset = Mock(return_value=base_queryset)
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_queryset()

        self.assertIs(result, base_queryset)
        policy_service.filter_queryset_by_active.assert_called_once_with(
            queryset=base_queryset,
            active_value="maybe",
        )

    def test_perform_create_saves_owner_id_when_user_is_under_limit(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        policy_service = Mock()
        policy_service.ensure_can_create_for_user.return_value = self.owner_id
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.policy_service_class = Mock(return_value=policy_service)

        view.perform_create(serializer)

        serializer.save.assert_called_once_with(owner_id=self.owner_id)
        policy_service.ensure_can_create_for_user.assert_called_once_with(self.user)

    def test_perform_create_rejects_sixth_schema_and_does_not_save(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        policy_service = Mock()
        policy_service.ensure_can_create_for_user.side_effect = CustomSchemaLimitExceededError(
            f"A user can only have up to {MAX_CUSTOM_SCHEMAS_PER_USER} custom schemas."
        )
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.policy_service_class = Mock(return_value=policy_service)

        with self.assertRaises(ValidationError) as context:
            view.perform_create(serializer)

        self.assertIn("message", context.exception.detail)
        serializer.save.assert_not_called()

    def test_detail_view_uses_user_scoped_queryset(self):
        view = CustomSchemaDetailView()
        base_queryset = Mock()
        policy_service = Mock()
        policy_service.get_queryset_for_user.return_value = base_queryset
        view.request = SimpleNamespace(user=self.user)
        view.policy_service_class = Mock(return_value=policy_service)

        result = view.get_queryset()

        self.assertIs(result, base_queryset)
        policy_service.get_queryset_for_user.assert_called_once_with(self.user)
