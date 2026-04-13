from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.core.signing import SignatureExpired, BadSignature
from rest_framework.test import APISimpleTestCase, APITestCase
from rest_framework import status

from authentication.models import User
from authentication.services import generate_verification_token


class VerifyEmailViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/verify-email/"
        self.valid_payload = {
            "token": "signed-token-string",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }

    @patch("authentication.views.User")
    @patch("authentication.views.decode_verification_token")
    def test_valid_token_with_strong_password_sets_password_and_verifies_user(
        self, mock_decode_token, mock_user_model
    ):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        mock_user = MagicMock()
        mock_user.status = "unverified"
        mock_user.email_verification_nonce = "nonce-123"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Email verified successfully")
        mock_user.set_password.assert_called_once_with("Strong#123")
        self.assertEqual(mock_user.status, "verified")
        mock_user.save.assert_called_once()

    @patch("authentication.views.decode_verification_token")
    def test_expired_token_returns_410(self, mock_decode_token):
        mock_decode_token.side_effect = SignatureExpired("Token expired")

        payload = {
            "token": "expired-token",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn("expired", response.data["message"].lower())

    @patch("authentication.views.decode_verification_token")
    def test_invalid_token_returns_400(self, mock_decode_token):
        mock_decode_token.side_effect = BadSignature("Bad token")

        payload = {
            "token": "tampered-token",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_token_param_returns_400(self):
        payload = {
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    @patch("authentication.views.User")
    def test_token_valid_but_user_not_found_returns_404(
        self, mock_user_model, mock_decode_token
    ):
        mock_decode_token.return_value = ("ghost@example.com", "nonce-123")
        mock_user_model.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_user_model.objects.get.side_effect = mock_user_model.DoesNotExist

        payload = {
            "token": "valid-but-no-user",
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("authentication.views.decode_verification_token")
    def test_password_too_short_returns_400(self, mock_decode_token):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        payload = {
            "token": "signed-token-string",
            "password": "S#1a",
            "password_confirm": "S#1a",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    def test_password_without_letter_returns_400(self, mock_decode_token):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        payload = {
            "token": "signed-token-string",
            "password": "1234567#",
            "password_confirm": "1234567#",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    def test_password_without_digit_returns_400(self, mock_decode_token):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        payload = {
            "token": "signed-token-string",
            "password": "Abcdefg#",
            "password_confirm": "Abcdefg#",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    def test_password_without_special_character_returns_400(self, mock_decode_token):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        payload = {
            "token": "signed-token-string",
            "password": "Abcdefg1",
            "password_confirm": "Abcdefg1",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    def test_password_confirmation_mismatch_returns_400(self, mock_decode_token):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        payload = {
            "token": "signed-token-string",
            "password": "Strong#123",
            "password_confirm": "Strong#124",
        }

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.decode_verification_token")
    @patch("authentication.views.User")
    def test_already_verified_user_cannot_reuse_token(
        self, mock_user_model, mock_decode_token
    ):
        mock_decode_token.return_value = ("user@example.com", "nonce-123")

        mock_user = MagicMock()
        mock_user.status = "verified"
        mock_user.email_verification_nonce = "nonce-123"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already verified", response.data["message"].lower())

    @patch("authentication.views.decode_verification_token")
    @patch("authentication.views.User")
    def test_stale_nonce_returns_invalid_token(
        self, mock_user_model, mock_decode_token
    ):
        mock_decode_token.return_value = ("user@example.com", "stale-nonce")

        mock_user = MagicMock()
        mock_user.status = "unverified"
        mock_user.email_verification_nonce = "fresh-nonce"
        mock_user_model.objects.get.return_value = mock_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Invalid token")


class ValidateVerificationTokenViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/verify-email/validate/"

    @patch("authentication.views.VerifyEmailView.validate_token")
    def test_valid_token_returns_200(self, mock_validate_token):
        mock_validate_token.return_value = MagicMock()

        response = self.client.post(
            self.url,
            {"token": "signed-token-string"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Verification token is valid")

    @patch("authentication.views.VerifyEmailView.validate_token")
    def test_invalid_token_bubbles_up_response(self, mock_validate_token):
        mock_validate_token.return_value = Response(
            {"message": "Invalid token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

        response = self.client.post(
            self.url,
            {"token": "bad-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Invalid token")

    def test_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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


class VerificationTokenLifecycleTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/verify-email/"
        self.user = User.objects.create_user(
            email="lifecycle@example.com",
            name="Lifecycle User",
            status="unverified",
        )
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])

    def test_token_cannot_be_reused_after_successful_verification(self):
        token = generate_verification_token(
            self.user.email,
            str(self.user.email_verification_nonce),
        )
        payload = {
            "token": token,
            "password": "Strong#123",
            "password_confirm": "Strong#123",
        }

        first_response = self.client.post(self.url, payload, format="json")
        second_response = self.client.post(self.url, payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already verified", second_response.data["message"].lower())

    def test_old_token_becomes_invalid_after_resend(self):
        old_token = generate_verification_token(
            self.user.email,
            str(self.user.email_verification_nonce),
        )

        resend_response = self.client.post(
            "/auth/resend-verification/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(resend_response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertNotEqual(str(self.user.email_verification_nonce), "")

        old_token_response = self.client.post(
            self.url,
            {
                "token": old_token,
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        new_token = generate_verification_token(
            self.user.email,
            str(self.user.email_verification_nonce),
        )
        new_token_response = self.client.post(
            self.url,
            {
                "token": new_token,
                "password": "Strong#123",
                "password_confirm": "Strong#123",
            },
            format="json",
        )

        self.assertEqual(old_token_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(old_token_response.data["message"], "Invalid token")
        self.assertEqual(new_token_response.status_code, status.HTTP_200_OK)
