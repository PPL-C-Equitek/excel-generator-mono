import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from custom_schemas.services import (
    CustomSchemaApplicationService,
    CustomSchemaLimitExceededError,
)
from custom_schemas.views import (
    CustomSchemaDetailView,
    CustomSchemaListCreateView,
)


class CustomSchemaViewUnitTest(SimpleTestCase):
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.user = SimpleNamespace(id=self.owner_id, is_authenticated=True)

    def test_get_current_user_id_delegates_to_policy_service(self):
        view = CustomSchemaListCreateView()
        application_service = Mock()
        application_service.get_owner_id.return_value = self.owner_id
        view.request = SimpleNamespace(user=self.user)
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_current_user_id()

        self.assertEqual(result, self.owner_id)
        application_service.get_owner_id.assert_called_once_with(self.user)

    def test_get_base_queryset_returns_none_for_unauthenticated_user(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(
            user=SimpleNamespace(id=None, is_authenticated=False)
        )
        application_service = Mock()
        application_service.get_queryset_for_user.return_value = "empty-queryset"
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_base_queryset()

        self.assertEqual(result, "empty-queryset")
        application_service.get_queryset_for_user.assert_called_once_with(
            view.request.user
        )

    def test_get_base_queryset_filters_by_current_owner_id(self):
        view = CustomSchemaListCreateView()
        view.request = SimpleNamespace(user=self.user)
        application_service = Mock()
        application_service.get_queryset_for_user.return_value = "owner-queryset"
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_base_queryset()

        self.assertEqual(result, "owner-queryset")
        application_service.get_queryset_for_user.assert_called_once_with(self.user)

    def test_list_view_filters_active_true_values(self):
        view = CustomSchemaListCreateView()
        application_service = Mock()
        application_service.get_filtered_queryset_for_user.return_value = "active-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "YES"})
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_queryset()

        self.assertEqual(result, "active-queryset")
        application_service.get_filtered_queryset_for_user.assert_called_once_with(
            user=self.user,
            active_value="YES",
        )

    def test_list_view_filters_active_false_values(self):
        view = CustomSchemaListCreateView()
        application_service = Mock()
        application_service.get_filtered_queryset_for_user.return_value = (
            "inactive-queryset"
        )
        view.request = SimpleNamespace(user=self.user, query_params={"active": "0"})
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_queryset()

        self.assertEqual(result, "inactive-queryset")
        application_service.get_filtered_queryset_for_user.assert_called_once_with(
            user=self.user,
            active_value="0",
        )

    def test_list_view_ignores_invalid_active_value(self):
        view = CustomSchemaListCreateView()
        application_service = Mock()
        application_service.get_filtered_queryset_for_user.return_value = "base-queryset"
        view.request = SimpleNamespace(user=self.user, query_params={"active": "maybe"})
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_queryset()

        self.assertEqual(result, "base-queryset")
        application_service.get_filtered_queryset_for_user.assert_called_once_with(
            user=self.user,
            active_value="maybe",
        )

    def test_perform_create_saves_owner_id_when_user_is_under_limit(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        application_service = Mock()
        application_service.get_create_owner_id.return_value = self.owner_id
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.application_service_class = Mock(return_value=application_service)

        view.perform_create(serializer)

        serializer.save.assert_called_once_with(owner_id=self.owner_id)
        application_service.get_create_owner_id.assert_called_once_with(self.user)

    def test_perform_create_rejects_sixth_schema_and_does_not_save(self):
        view = CustomSchemaListCreateView()
        serializer = Mock()
        application_service = Mock()
        application_service.get_create_owner_id.side_effect = CustomSchemaLimitExceededError(
            "limit reached"
        )
        application_service.get_limit_exceeded_message.return_value = "limit reached"
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.application_service_class = Mock(return_value=application_service)

        with self.assertRaises(ValidationError) as context:
            view.perform_create(serializer)

        self.assertIn("message", context.exception.detail)
        self.assertEqual(context.exception.detail["message"], "limit reached")
        serializer.save.assert_not_called()

    def test_detail_view_uses_user_scoped_queryset(self):
        view = CustomSchemaDetailView()
        base_queryset = Mock()
        application_service = Mock()
        application_service.get_queryset_for_user.return_value = base_queryset
        view.request = SimpleNamespace(user=self.user)
        view.application_service_class = Mock(return_value=application_service)

        result = view.get_queryset()

        self.assertIs(result, base_queryset)
        application_service.get_queryset_for_user.assert_called_once_with(self.user)

    def test_get_serializer_context_injects_application_service(self):
        view = CustomSchemaListCreateView()
        application_service = Mock(spec=CustomSchemaApplicationService)
        view.request = SimpleNamespace(user=self.user, query_params={})
        view.args = ()
        view.kwargs = {}
        view.format_kwarg = None
        view.application_service_class = Mock(return_value=application_service)

        context = view.get_serializer_context()

        self.assertIs(context["application_service"], application_service)
        self.assertIs(context["request"], view.request)
