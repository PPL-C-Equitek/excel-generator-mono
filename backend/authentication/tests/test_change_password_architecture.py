from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.test import (
    APISimpleTestCase,
    APIRequestFactory,
    force_authenticate,
)

from authentication.change_password.constants import (
    CHANGE_PASSWORD_CURRENT_PASSWORD_REQUIRED_MESSAGE,
    CHANGE_PASSWORD_INVALID_CURRENT_PASSWORD_MESSAGE,
    CHANGE_PASSWORD_PASSWORD_REUSE_MESSAGE,
    CHANGE_PASSWORD_SERVER_ERROR_MESSAGE,
    CHANGE_PASSWORD_SUCCESS_MESSAGE,
)
from authentication.change_password.entities import (
    ChangePasswordCommand,
    ChangePasswordResult,
)
from authentication.change_password.exceptions import (
    ChangePasswordServiceError,
    CurrentPasswordRequiredError,
    InvalidCurrentPasswordError,
    PasswordReuseError,
)
from authentication.change_password.http import ChangePasswordView
from authentication.change_password.use_cases import DefaultChangePasswordUseCase
from authentication.models import User


class DefaultChangePasswordUseCaseTest(APISimpleTestCase):
    def setUp(self):
        self.user = User(
            email="user@example.com",
            name="User",
            status="verified",
        )

    def test_requires_current_password_for_users_with_usable_password(self):
        account_port = MagicMock()
        account_port.has_usable_password.return_value = True
        notification_port = MagicMock()
        blacklist_port = MagicMock()
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=notification_port,
            token_blacklist_port=blacklist_port,
        )

        with self.assertRaises(CurrentPasswordRequiredError):
            use_case.execute(
                ChangePasswordCommand(
                    user=self.user,
                    current_password="",
                    new_password="Updated#123",
                )
            )

    def test_rejects_invalid_current_password(self):
        account_port = MagicMock()
        account_port.has_usable_password.return_value = True
        account_port.check_password.side_effect = [False]
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=MagicMock(),
            token_blacklist_port=MagicMock(),
        )

        with self.assertRaises(InvalidCurrentPasswordError):
            use_case.execute(
                ChangePasswordCommand(
                    user=self.user,
                    current_password="Wrong#123",
                    new_password="Updated#123",
                )
            )

    def test_rejects_password_reuse(self):
        account_port = MagicMock()
        account_port.has_usable_password.return_value = True
        account_port.check_password.side_effect = [True, True]
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=MagicMock(),
            token_blacklist_port=MagicMock(),
        )

        with self.assertRaises(PasswordReuseError):
            use_case.execute(
                ChangePasswordCommand(
                    user=self.user,
                    current_password="Current#123",
                    new_password="Current#123",
                )
            )

    def test_changes_password_for_google_user_without_current_password(self):
        account_port = MagicMock()
        account_port.has_usable_password.return_value = False
        account_port.check_password.return_value = False
        notification_port = MagicMock()
        blacklist_port = MagicMock()
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=notification_port,
            token_blacklist_port=blacklist_port,
        )

        result = use_case.execute(
            ChangePasswordCommand(
                user=self.user,
                current_password="",
                new_password="Updated#123",
            )
        )

        self.assertEqual(
            result,
            ChangePasswordResult(message=CHANGE_PASSWORD_SUCCESS_MESSAGE),
        )
        account_port.set_password.assert_called_once_with(self.user, "Updated#123")
        notification_port.send_password_changed_email.assert_called_once_with(
            "user@example.com"
        )

    def test_blacklist_and_notification_failures_are_best_effort(self):
        account_port = MagicMock()
        account_port.has_usable_password.return_value = False
        account_port.check_password.return_value = False
        notification_port = MagicMock()
        notification_port.send_password_changed_email.side_effect = RuntimeError(
            "mail down"
        )
        blacklist_port = MagicMock()
        blacklist_port.blacklist.side_effect = ValueError("bad refresh token")
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=notification_port,
            token_blacklist_port=blacklist_port,
        )

        result = use_case.execute(
            ChangePasswordCommand(
                user=self.user,
                current_password="",
                new_password="Updated#123",
                refresh_token="bad-token",
            )
        )

        self.assertEqual(result.message, CHANGE_PASSWORD_SUCCESS_MESSAGE)
        account_port.set_password.assert_called_once()

    def test_wraps_unexpected_errors(self):
        account_port = MagicMock()
        account_port.has_usable_password.side_effect = RuntimeError("db down")
        use_case = DefaultChangePasswordUseCase(
            account_port=account_port,
            notification_port=MagicMock(),
            token_blacklist_port=MagicMock(),
        )

        with self.assertRaises(ChangePasswordServiceError):
            use_case.execute(
                ChangePasswordCommand(
                    user=self.user,
                    current_password="Current#123",
                    new_password="Updated#123",
                )
            )


class ChangePasswordViewDependencyInjectionTest(APISimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User(
            email="user@example.com",
            name="User",
            status="verified",
        )
        self.user.set_password("Current#123")

    def test_view_delegates_to_injected_use_case(self):
        use_case = MagicMock()
        use_case.execute.return_value = ChangePasswordResult(
            message=CHANGE_PASSWORD_SUCCESS_MESSAGE
        )

        class TestableChangePasswordView(ChangePasswordView):
            def get_change_password_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/change-password/",
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
                "refresh_token": "refresh-token",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TestableChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case.execute.assert_called_once_with(
            ChangePasswordCommand(
                user=self.user,
                current_password="Current#123",
                new_password="Updated#123",
                refresh_token="refresh-token",
            )
        )

    def test_view_maps_current_password_required_error(self):
        use_case = MagicMock()
        use_case.execute.side_effect = CurrentPasswordRequiredError()

        class TestableChangePasswordView(ChangePasswordView):
            def get_change_password_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/change-password/",
            {
                "current_password": "",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TestableChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            CHANGE_PASSWORD_CURRENT_PASSWORD_REQUIRED_MESSAGE,
        )

    def test_view_maps_invalid_current_password_error(self):
        use_case = MagicMock()
        use_case.execute.side_effect = InvalidCurrentPasswordError()

        class TestableChangePasswordView(ChangePasswordView):
            def get_change_password_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/change-password/",
            {
                "current_password": "Wrong#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TestableChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            CHANGE_PASSWORD_INVALID_CURRENT_PASSWORD_MESSAGE,
        )

    def test_view_maps_password_reuse_error(self):
        use_case = MagicMock()
        use_case.execute.side_effect = PasswordReuseError()

        class TestableChangePasswordView(ChangePasswordView):
            def get_change_password_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/change-password/",
            {
                "current_password": "Current#123",
                "new_password": "Current#123",
                "new_password_confirm": "Current#123",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TestableChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            CHANGE_PASSWORD_PASSWORD_REUSE_MESSAGE,
        )

    def test_view_returns_500_when_use_case_raises_application_error(self):
        use_case = MagicMock()
        use_case.execute.side_effect = ChangePasswordServiceError("boom")

        class TestableChangePasswordView(ChangePasswordView):
            def get_change_password_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/change-password/",
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = TestableChangePasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.data["message"],
            CHANGE_PASSWORD_SERVER_ERROR_MESSAGE,
        )
