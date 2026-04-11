from __future__ import annotations

from unittest.mock import MagicMock

from django.core.signing import BadSignature, SignatureExpired
from rest_framework import status
from rest_framework.test import APISimpleTestCase, APIRequestFactory

from authentication.password_reset.constants import (
    PASSWORD_RESET_COMPLETED_MESSAGE,
    PASSWORD_RESET_EXPIRED_TOKEN_MESSAGE,
    PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
    PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE,
    PASSWORD_RESET_SERVER_ERROR_MESSAGE,
    PASSWORD_RESET_USER_NOT_FOUND_MESSAGE,
)
from authentication.password_reset.entities import (
    CompletePasswordResetCommand,
    PasswordResetEmailCommand,
    PasswordResetResult,
)
from authentication.password_reset.exceptions import (
    InvalidPasswordResetTokenError,
    PasswordResetServiceError,
    PasswordResetTokenExpiredError,
    PasswordResetUserNotFoundError,
)
from authentication.password_reset.http import (
    ForgotPasswordView,
    ResetPasswordView,
)
from authentication.password_reset.use_cases import (
    DefaultCompletePasswordResetUseCase,
    DefaultRequestPasswordResetUseCase,
)


class PasswordResetCommandTest(APISimpleTestCase):
    def test_email_command_normalizes_email(self):
        command = PasswordResetEmailCommand(email="  User@Example.COM  ")

        self.assertEqual(command.email, "user@example.com")


class DefaultRequestPasswordResetUseCaseTest(APISimpleTestCase):
    def test_sends_email_when_verified_user_exists(self):
        lookup = MagicMock()
        lookup.has_verified_user.return_value = True
        notifier = MagicMock()
        use_case = DefaultRequestPasswordResetUseCase(
            lookup_port=lookup,
            notification_port=notifier,
        )

        result = use_case.execute(PasswordResetEmailCommand(email="user@example.com"))

        self.assertEqual(
            result,
            PasswordResetResult(message=PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE),
        )
        lookup.has_verified_user.assert_called_once_with("user@example.com")
        notifier.send_password_reset_email.assert_called_once_with("user@example.com")

    def test_returns_generic_success_without_sending_for_unknown_email(self):
        lookup = MagicMock()
        lookup.has_verified_user.return_value = False
        notifier = MagicMock()
        use_case = DefaultRequestPasswordResetUseCase(
            lookup_port=lookup,
            notification_port=notifier,
        )

        result = use_case.execute(PasswordResetEmailCommand(email="user@example.com"))

        self.assertEqual(result.message, PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE)
        notifier.send_password_reset_email.assert_not_called()

    def test_wraps_unexpected_errors(self):
        lookup = MagicMock()
        lookup.has_verified_user.side_effect = RuntimeError("db down")
        notifier = MagicMock()
        use_case = DefaultRequestPasswordResetUseCase(
            lookup_port=lookup,
            notification_port=notifier,
        )

        with self.assertRaises(PasswordResetServiceError):
            use_case.execute(PasswordResetEmailCommand(email="user@example.com"))


class DefaultCompletePasswordResetUseCaseTest(APISimpleTestCase):
    def test_resets_password_when_token_is_valid_and_user_exists(self):
        decoder = MagicMock()
        decoder.decode.return_value = "user@example.com"
        account_port = MagicMock()
        account_port.reset_password_for_verified_user.return_value = True
        use_case = DefaultCompletePasswordResetUseCase(
            token_decoder_port=decoder,
            account_port=account_port,
        )

        result = use_case.execute(
            CompletePasswordResetCommand(
                token="signed-token",
                password="Strong#123",
            )
        )

        self.assertEqual(result.message, PASSWORD_RESET_COMPLETED_MESSAGE)
        account_port.reset_password_for_verified_user.assert_called_once_with(
            "user@example.com",
            "Strong#123",
        )

    def test_maps_expired_token(self):
        decoder = MagicMock()
        decoder.decode.side_effect = SignatureExpired("expired")
        account_port = MagicMock()
        use_case = DefaultCompletePasswordResetUseCase(
            token_decoder_port=decoder,
            account_port=account_port,
        )

        with self.assertRaises(PasswordResetTokenExpiredError):
            use_case.execute(
                CompletePasswordResetCommand(
                    token="signed-token",
                    password="Strong#123",
                )
            )

    def test_maps_invalid_token(self):
        decoder = MagicMock()
        decoder.decode.side_effect = BadSignature("bad")
        account_port = MagicMock()
        use_case = DefaultCompletePasswordResetUseCase(
            token_decoder_port=decoder,
            account_port=account_port,
        )

        with self.assertRaises(InvalidPasswordResetTokenError):
            use_case.execute(
                CompletePasswordResetCommand(
                    token="signed-token",
                    password="Strong#123",
                )
            )

    def test_raises_user_not_found_when_repository_reports_missing_user(self):
        decoder = MagicMock()
        decoder.decode.return_value = "ghost@example.com"
        account_port = MagicMock()
        account_port.reset_password_for_verified_user.return_value = False
        use_case = DefaultCompletePasswordResetUseCase(
            token_decoder_port=decoder,
            account_port=account_port,
        )

        with self.assertRaises(PasswordResetUserNotFoundError):
            use_case.execute(
                CompletePasswordResetCommand(
                    token="signed-token",
                    password="Strong#123",
                )
            )

    def test_wraps_unexpected_account_errors(self):
        decoder = MagicMock()
        decoder.decode.return_value = "user@example.com"
        account_port = MagicMock()
        account_port.reset_password_for_verified_user.side_effect = RuntimeError("db down")
        use_case = DefaultCompletePasswordResetUseCase(
            token_decoder_port=decoder,
            account_port=account_port,
        )

        with self.assertRaises(PasswordResetServiceError):
            use_case.execute(
                CompletePasswordResetCommand(
                    token="signed-token",
                    password="Strong#123",
                )
            )


class PasswordResetViewDependencyInjectionTest(APISimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_forgot_password_view_delegates_to_injected_use_case(self):
        use_case = MagicMock()
        use_case.execute.return_value = PasswordResetResult(
            message=PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE
        )

        class TestableForgotPasswordView(ForgotPasswordView):
            def get_request_password_reset_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/forgot-password/",
            {"email": "  User@Example.COM  "},
            format="json",
        )

        response = TestableForgotPasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case.execute.assert_called_once_with(
            PasswordResetEmailCommand(email="user@example.com")
        )

    def test_forgot_password_view_returns_500_for_application_error(self):
        use_case = MagicMock()
        use_case.execute.side_effect = PasswordResetServiceError("boom")

        class TestableForgotPasswordView(ForgotPasswordView):
            def get_request_password_reset_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/forgot-password/",
            {"email": "user@example.com"},
            format="json",
        )

        response = TestableForgotPasswordView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], PASSWORD_RESET_SERVER_ERROR_MESSAGE)

    def test_reset_password_view_maps_domain_errors(self):
        class ExpiredView(ResetPasswordView):
            def get_complete_password_reset_use_case(self):  # type: ignore[override]
                use_case = MagicMock()
                use_case.execute.side_effect = PasswordResetTokenExpiredError()
                return use_case

        request = self.factory.post(
            "/auth/reset-password/",
            {
                "token": "signed-token",
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        response = ExpiredView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["message"], PASSWORD_RESET_EXPIRED_TOKEN_MESSAGE)

    def test_reset_password_view_maps_invalid_token(self):
        class InvalidView(ResetPasswordView):
            def get_complete_password_reset_use_case(self):  # type: ignore[override]
                use_case = MagicMock()
                use_case.execute.side_effect = InvalidPasswordResetTokenError()
                return use_case

        request = self.factory.post(
            "/auth/reset-password/",
            {
                "token": "signed-token",
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        response = InvalidView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    def test_reset_password_view_maps_missing_user(self):
        class MissingUserView(ResetPasswordView):
            def get_complete_password_reset_use_case(self):  # type: ignore[override]
                use_case = MagicMock()
                use_case.execute.side_effect = PasswordResetUserNotFoundError()
                return use_case

        request = self.factory.post(
            "/auth/reset-password/",
            {
                "token": "signed-token",
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        response = MissingUserView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], PASSWORD_RESET_USER_NOT_FOUND_MESSAGE)
