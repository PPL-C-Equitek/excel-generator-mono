from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.core.signing import SignatureExpired, BadSignature
from rest_framework.test import APISimpleTestCase
from rest_framework import status


class VerifyEmailViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/verify-email/"

    @patch("authentication.views.User")
    @patch("authentication.views.TimestampSigner")
    def test_valid_token_verifies_user_returns_200(
        self, mock_signer_cls, mock_user_model
    ):
        mock_signer = MagicMock()
        mock_signer_cls.return_value = mock_signer
        mock_signer.unsign.return_value = "user@example.com"

        mock_user = MagicMock()
        mock_user.status = "unverified"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.get(self.url, {"token": "signed-token-string"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Email verified successfully")
        self.assertEqual(mock_user.status, "verified")
        mock_user.save.assert_called_once()

    @patch("authentication.views.TimestampSigner")
    def test_expired_token_returns_410(self, mock_signer_cls):
        mock_signer = MagicMock()
        mock_signer_cls.return_value = mock_signer
        mock_signer.unsign.side_effect = SignatureExpired("Token expired")

        response = self.client.get(self.url, {"token": "expired-token"})

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn("expired", response.data["message"].lower())

    @patch("authentication.views.TimestampSigner")
    def test_invalid_token_returns_400(self, mock_signer_cls):
        mock_signer = MagicMock()
        mock_signer_cls.return_value = mock_signer
        mock_signer.unsign.side_effect = BadSignature("Bad token")

        response = self.client.get(self.url, {"token": "tampered-token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_token_param_returns_400(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.TimestampSigner")
    @patch("authentication.views.User")
    def test_token_valid_but_user_not_found_returns_404(
        self, mock_user_model, mock_signer_cls
    ):
        mock_signer = MagicMock()
        mock_signer_cls.return_value = mock_signer
        mock_signer.unsign.return_value = "ghost@example.com"
        mock_user_model.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_user_model.objects.get.side_effect = mock_user_model.DoesNotExist

        response = self.client.get(self.url, {"token": "valid-but-no-user"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("authentication.views.User")
    @patch("authentication.views.TimestampSigner")
    def test_already_verified_user_returns_200_idempotent(
        self, mock_signer_cls, mock_user_model
    ):
        mock_signer = MagicMock()
        mock_signer_cls.return_value = mock_signer
        mock_signer.unsign.return_value = "verified@example.com"

        mock_user = MagicMock()
        mock_user.status = "verified"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.get(self.url, {"token": "already-verified-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)


# -------------------------------------------------------------------- #
# POST /auth/resend-verification
# -------------------------------------------------------------------- #
class ResendVerificationViewTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/resend-verification/"

    @patch("authentication.views.send_verification_email")
    @patch("authentication.views.User")
    def test_resend_to_unverified_user_returns_200(
        self, mock_user_model, mock_send_email
    ):
        mock_user = MagicMock()
        mock_user.status = "unverified"
        mock_user.email = "unverified@example.com"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.post(
            self.url,
            {"email": "unverified@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        mock_send_email.assert_called_once()

    @patch("authentication.views.User")
    def test_resend_to_verified_user_returns_400(self, mock_user_model):
        mock_user = MagicMock()
        mock_user.status = "verified"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.post(
            self.url,
            {"email": "verified@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already verified", response.data["message"].lower())

    @patch("authentication.views.User")
    def test_resend_to_nonexistent_email_returns_404(self, mock_user_model):
        mock_user_model.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_user_model.objects.get.side_effect = mock_user_model.DoesNotExist

        response = self.client.post(
            self.url,
            {"email": "nobody@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_resend_missing_email_field_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.send_verification_email")
    @patch("authentication.views.User")
    def test_resend_rate_limit_returns_429_on_4th_request(
        self, mock_user_model, mock_send_email
    ):
        mock_user = MagicMock()
        mock_user.status = "unverified"
        mock_user.email = "ratelimit@example.com"
        mock_user_model.objects.get.return_value = mock_user

        payload = {"email": "ratelimit@example.com"}

        for i in range(3):
            resp = self.client.post(self.url, payload, format="json")
            self.assertEqual(
                resp.status_code,
                status.HTTP_200_OK,
                f"Request {i + 1} should succeed but got {resp.status_code}",
            )

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
