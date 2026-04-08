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
    def test_logs_password_reset_link_when_no_api_key(self):
        with self.assertLogs("authentication.services", level="INFO") as log:
            send_password_reset_email("user@example.com")

        log_text = "\n".join(log.output)
        self.assertIn("Password reset link", log_text)
        self.assertIn("reset-password?token=", log_text)

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
    def test_nonexistent_email_returns_generic_success_without_sending(
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
        self.assertEqual(response.data["message"], PASSWORD_RESET_SUCCESS_MESSAGE)
        mock_send_email.assert_not_called()

    @patch("authentication.password_reset.adapters.send_password_reset_email")
    @patch("authentication.password_reset.adapters.User")
    def test_unverified_user_returns_generic_success_without_sending(
        self, mock_user_model, mock_send_email
    ):
        mock_queryset = MagicMock()
        mock_queryset.exists.return_value = False
        mock_user_model.objects.filter.return_value = mock_queryset

        response = self.client.post(
            self.url,
            {"email": "pending@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], PASSWORD_RESET_SUCCESS_MESSAGE)
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


class ResetPasswordViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/reset-password/"
        self.valid_payload = {
            "token": "signed-reset-token",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
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
