import sys
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APISimpleTestCase

from authentication.services import (
    PASSWORD_RESET_RESEND_SUCCESS_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
    decode_password_reset_token,
    generate_password_reset_token,
    send_password_reset_email,
)
from authentication.password_reset.entities import CompletePasswordResetCommand
from authentication.password_reset.exceptions import PasswordResetServiceError
from authentication.password_reset.use_cases import DefaultCompletePasswordResetUseCase


class GeneratePasswordResetTokenTest(SimpleTestCase):
    def test_generates_signed_token_containing_password_reset_scope(self):
        token = generate_password_reset_token("user@example.com")

        email = decode_password_reset_token(token, max_age=60)

        self.assertEqual(email, "user@example.com")

    def test_rejects_token_with_different_scope(self):
        from django.core.signing import TimestampSigner

        token = TimestampSigner().sign("verification:user@example.com")

        with self.assertRaises(ValueError):
            decode_password_reset_token(token, max_age=60)


class SendPasswordResetEmailTest(SimpleTestCase):
    @override_settings(RESEND_API_KEY="", FRONTEND_URL="http://localhost:3000")
    def test_logs_password_reset_request_without_exposing_reset_link_when_no_api_key(self):
        with self.assertLogs("authentication.services", level="INFO") as log:
            send_password_reset_email("user@example.com")

        log_text = "\n".join(log.output)
        self.assertIn("Password reset requested for user@example.com", log_text)
        self.assertNotIn("reset-password?token=", log_text)

    @override_settings(
        RESEND_API_KEY="re_test_key",
        FRONTEND_URL="https://app.example.com",
        RESEND_FROM_EMAIL="noreply@app.example.com",
    )
    def test_sends_password_reset_email_via_resend_when_api_key_configured(self):
        mock_resend = MagicMock()
        with patch.dict(sys.modules, {"resend": mock_resend}):
            send_password_reset_email("user@example.com")

        self.assertEqual(mock_resend.api_key, "re_test_key")
        mock_resend.Emails.send.assert_called_once()

        call_kwargs = mock_resend.Emails.send.call_args[0][0]
        self.assertEqual(call_kwargs["from"], "noreply@app.example.com")
        self.assertEqual(call_kwargs["to"], "user@example.com")
        self.assertEqual(call_kwargs["subject"], "Reset Your Password")
        self.assertIn("reset-password?token=", call_kwargs["html"])

    @override_settings(
        RESEND_API_KEY="re_test_key",
        FRONTEND_URL="https://app.example.com",
        RESEND_FROM_EMAIL="noreply@app.example.com",
    )
    def test_raises_when_resend_email_send_fails(self):
        mock_resend = MagicMock()
        mock_resend.Emails.send.side_effect = RuntimeError("send failed")

        with patch.dict(sys.modules, {"resend": mock_resend}):
            with self.assertRaisesRegex(RuntimeError, "send failed"):
                send_password_reset_email("user@example.com")


class ForgotPasswordViewTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/forgot-password/"

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_verified_user_receives_password_reset_email(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(
            self.url,
            {"email": "verified@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], PASSWORD_RESET_SUCCESS_MESSAGE)
        mock_send_email.assert_called_once_with("verified@example.com")

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_unknown_or_unverified_email_returns_generic_success_without_sending(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_user_model.objects.filter.return_value = mock_queryset

        for payload in (
            {"email": "missing@example.com"},
            {"email": "pending@example.com"},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["message"], PASSWORD_RESET_SUCCESS_MESSAGE)
        mock_send_email.assert_not_called()

    def test_missing_email_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_rate_limit_blocks_on_4th_request_for_email_identity_partitions(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset

        identity_partitions = (
            {
                "name": "exact_same_email",
                "payloads": (
                    {"email": "ratelimit@example.com"},
                    {"email": "ratelimit@example.com"},
                    {"email": "ratelimit@example.com"},
                ),
                "blocked_payload": {"email": "ratelimit@example.com"},
            },
            {
                "name": "normalized_case_and_whitespace_email",
                "payloads": (
                    {"email": "  RateLimit@Example.com  "},
                    {"email": "ratelimit@example.com"},
                    {"email": "RATELIMIT@example.com"},
                ),
                "blocked_payload": {"email": "ratelimit@example.com"},
            },
        )
        for partition in identity_partitions:
            with self.subTest(partition=partition["name"]):
                cache.clear()

                for payload in partition["payloads"]:
                    response = self.client.post(self.url, payload, format="json")
                    self.assertEqual(response.status_code, status.HTTP_200_OK)

                blocked_response = self.client.post(
                    self.url,
                    partition["blocked_payload"],
                    format="json",
                )
                self.assertEqual(
                    blocked_response.status_code,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                )

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_rate_limit_normalizes_email_identity_across_case_and_whitespace(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset

        payload_variants = (
            {"email": "  RateLimit@Example.com  "},
            {"email": "ratelimit@example.com"},
            {"email": "RATELIMIT@example.com"},
        )

        for payload in payload_variants:
            response = self.client.post(self.url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        blocked_response = self.client.post(
            self.url,
            {"email": "ratelimit@example.com"},
            format="json",
        )
        self.assertEqual(blocked_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("authentication.password_reset.http.ForgotPasswordView.get_request_password_reset_use_case")
    def test_error_partitions_return_500(self, mock_get_use_case):
        for error in (
            PasswordResetServiceError("boom"),
            RuntimeError("boom"),
        ):
            with self.subTest(error=type(error).__name__):
                mock_use_case = MagicMock()
                mock_use_case.execute.side_effect = error
                mock_get_use_case.return_value = mock_use_case

                response = self.client.post(
                    self.url,
                    {"email": "verified@example.com"},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.assertEqual(
                    response.data["message"],
                    "An internal server error occurred. Please try again later.",
                )


class ResendPasswordResetViewTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/resend-password-reset/"

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_verified_user_can_resend_password_reset_email(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(
            self.url,
            {"email": "verified@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"], PASSWORD_RESET_RESEND_SUCCESS_MESSAGE
        )
        mock_send_email.assert_called_once_with("verified@example.com")

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_nonexistent_email_returns_generic_resend_success(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(
            self.url,
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"], PASSWORD_RESET_RESEND_SUCCESS_MESSAGE
        )
        mock_send_email.assert_not_called()

    def test_missing_email_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_rate_limit_returns_429_on_4th_request(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset

        payload = {"email": "ratelimit@example.com"}

        for _ in range(3):
            response = self.client.post(self.url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("authentication.password_reset.http.ResendPasswordResetView.get_resend_password_reset_use_case")
    def test_error_partitions_return_500(self, mock_get_use_case):
        for error in (
            PasswordResetServiceError("boom"),
            RuntimeError("boom"),
        ):
            with self.subTest(error=type(error).__name__):
                mock_use_case = MagicMock()
                mock_use_case.execute.side_effect = error
                mock_get_use_case.return_value = mock_use_case

                response = self.client.post(
                    self.url,
                    {"email": "verified@example.com"},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.assertEqual(
                    response.data["message"],
                    "An internal server error occurred. Please try again later.",
                )


class PasswordResetThrottleScopeIsolationTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.forgot_url = "/auth/forgot-password/"
        self.resend_url = "/auth/resend-password-reset/"

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_forgot_and_resend_throttles_are_isolated_per_scope(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = True
        mock_user_model.objects.filter.return_value = mock_queryset
        payload = {"email": "scope@example.com"}

        for _ in range(3):
            response = self.client.post(self.forgot_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        forgot_blocked = self.client.post(self.forgot_url, payload, format="json")
        self.assertEqual(forgot_blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        for _ in range(3):
            response = self.client.post(self.resend_url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        resend_blocked = self.client.post(self.resend_url, payload, format="json")
        self.assertEqual(resend_blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(mock_send_email.call_count, 6)


class ResetPasswordViewTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/reset-password/"
        self.valid_payload = {
            "token": "signed-reset-token",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }

    def _build_payload(
        self,
        *,
        token: str,
        password: str = "Strong#123",
        password_confirm: str = "Strong#123",
    ):
        return {
            "token": token,
            "password": password,
            "password_confirm": password_confirm,
        }

    @patch("authentication.password_reset.adapters.decode_password_reset_token")
    @patch("authentication.password_reset.adapters.User")
    def test_valid_token_sets_new_password_for_verified_user(
        self, mock_user_model, mock_decode_token
    ):
        mock_decode_token.return_value = "user@example.com"
        mock_user = MagicMock()
        mock_queryset = MagicMock()
        mock_queryset.first.return_value = mock_user
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Password reset successfully")
        mock_user.set_password.assert_called_once_with("Strong#123")
        mock_user.save.assert_called_once_with(update_fields=["password"])
        mock_user_model.objects.filter.assert_called_once_with(
            email="user@example.com",
            status="verified",
        )

    @patch("authentication.password_reset.adapters.decode_password_reset_token")
    def test_expired_token_returns_410(self, mock_decode_token):
        mock_decode_token.side_effect = SignatureExpired("Expired")

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn("expired", response.data["message"].lower())

    @patch("authentication.password_reset.adapters.decode_password_reset_token")
    def test_invalid_token_returns_400(self, mock_decode_token):
        mock_decode_token.side_effect = BadSignature("Bad token")

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Invalid token")

    def test_missing_token_returns_400(self):
        response = self.client.post(
            self.url,
            {
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("authentication.password_reset.adapters.decode_password_reset_token")
    @patch("authentication.password_reset.adapters.User")
    def test_valid_token_but_user_not_found_returns_404(
        self, mock_user_model, mock_decode_token
    ):
        mock_decode_token.return_value = "ghost@example.com"
        mock_queryset = MagicMock()
        mock_queryset.first.return_value = None
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "User not found")

    def test_password_confirmation_mismatch_returns_400(self):
        response = self.client.post(
            self.url,
            {
                "token": "signed-reset-token",
                "password": "Strong#123",
                "password_confirm": "Strong#124",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("authentication.password_reset.http.ResetPasswordView.get_complete_password_reset_use_case")
    def test_rate_limit_returns_429_on_6th_request(self, mock_get_use_case):
        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = MagicMock(message="Password reset successfully")
        mock_get_use_case.return_value = mock_use_case

        for _ in range(5):
            response = self.client.post(self.url, self.valid_payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("authentication.password_reset.http.ResetPasswordView.get_complete_password_reset_use_case")
    def test_rate_limit_groups_tokens_by_first_16_chars_prefix(self, mock_get_use_case):
        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = MagicMock(message="Password reset successfully")
        mock_get_use_case.return_value = mock_use_case

        shared_prefix = "1234567890abcdef"
        payload_a = self._build_payload(token=f"{shared_prefix}-token-a")
        payload_b = self._build_payload(token=f"{shared_prefix}-token-b")

        for _ in range(5):
            response = self.client.post(self.url, payload_a, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        blocked_response = self.client.post(self.url, payload_b, format="json")
        self.assertEqual(blocked_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(mock_use_case.execute.call_count, 5)

    @patch("authentication.password_reset.http.ResetPasswordView.get_complete_password_reset_use_case")
    def test_rate_limit_separates_tokens_with_different_prefixes(self, mock_get_use_case):
        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = MagicMock(message="Password reset successfully")
        mock_get_use_case.return_value = mock_use_case

        payload_a = self._build_payload(token="1234567890abcdef-token-a")
        payload_b = self._build_payload(token="fedcba0987654321-token-b")

        for _ in range(5):
            response = self.client.post(self.url, payload_a, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_different_prefix = self.client.post(self.url, payload_b, format="json")
        self.assertEqual(response_different_prefix.status_code, status.HTTP_200_OK)

        blocked_response = self.client.post(self.url, payload_a, format="json")
        self.assertEqual(blocked_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(mock_use_case.execute.call_count, 6)

    def test_password_strength_isp_invalid_partitions_return_400(self):
        invalid_password_partitions = (
            {
                "name": "too_short",
                "password": "Aa1!",
            },
            {
                "name": "missing_letter",
                "password": "1234567!",
            },
            {
                "name": "missing_number",
                "password": "Password!",
            },
            {
                "name": "missing_special_character",
                "password": "Password1",
            },
        )

        for partition in invalid_password_partitions:
            with self.subTest(partition=partition["name"]):
                payload = self._build_payload(
                    token="signed-reset-token",
                    password=partition["password"],
                    password_confirm=partition["password"],
                )
                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("errors", response.data)
                self.assertIn("password", response.data["errors"])

    @patch("authentication.password_reset.http.ResetPasswordView.get_complete_password_reset_use_case")
    def test_error_partitions_return_500(self, mock_get_use_case):
        for error in (
            PasswordResetServiceError("boom"),
            RuntimeError("boom"),
        ):
            with self.subTest(error=type(error).__name__):
                mock_use_case = MagicMock()
                mock_use_case.execute.side_effect = error
                mock_get_use_case.return_value = mock_use_case

                response = self.client.post(self.url, self.valid_payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
                self.assertEqual(
                    response.data["message"],
                    "An internal server error occurred. Please try again later.",
                )


class CompletePasswordResetUseCaseTest(SimpleTestCase):
    def test_wraps_unexpected_decoder_errors_as_service_errors(self):
        token_decoder_port = MagicMock()
        token_decoder_port.decode.side_effect = RuntimeError("decoder exploded")
        account_port = MagicMock()
        use_case = DefaultCompletePasswordResetUseCase(token_decoder_port, account_port)

        with self.assertRaises(PasswordResetServiceError):
            use_case.execute(
                CompletePasswordResetCommand(
                    token="signed-reset-token",
                    password="Strong#123",
                )
            )
