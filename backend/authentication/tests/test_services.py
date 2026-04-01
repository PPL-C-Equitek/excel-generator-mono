import sys
import jwt
import uuid
from unittest.mock import patch, MagicMock
from django.utils import timezone

from django.core.signing import TimestampSigner
from django.test import SimpleTestCase, override_settings

from authentication.services import generate_verification_token, send_verification_email, generate_tokens

class GenerateVerificationTokenTest(SimpleTestCase):
    def test_generates_signed_token_containing_email(self):
        token = generate_verification_token("test@example.com")

        signer = TimestampSigner()
        email = signer.unsign(token, max_age=60)
        self.assertEqual(email, "test@example.com")

    def test_different_emails_produce_different_tokens(self):
        token_a = generate_verification_token("a@example.com")
        token_b = generate_verification_token("b@example.com")
        self.assertNotEqual(token_a, token_b)


class SendVerificationEmailTest(SimpleTestCase):
    @override_settings(RESEND_API_KEY="", FRONTEND_URL="http://localhost:3000")
    @patch("builtins.print")
    def test_prints_verification_link_when_no_api_key(self, mock_print):
        send_verification_email("user@example.com")

        mock_print.assert_called_once()
        printed_text = mock_print.call_args[0][0]
        self.assertIn("VERIFICATION LINK", printed_text)
        self.assertIn("verify-email?token=", printed_text)

    @override_settings(
        RESEND_API_KEY="re_test_key",
        FRONTEND_URL="https://app.example.com",
        RESEND_FROM_EMAIL="noreply@app.example.com",
    )
    def test_sends_email_via_resend_when_api_key_configured(self):
        mock_resend = MagicMock()
        with patch.dict(sys.modules, {"resend": mock_resend}):
            send_verification_email("user@example.com")

        self.assertEqual(mock_resend.api_key, "re_test_key")
        mock_resend.Emails.send.assert_called_once()

        call_kwargs = mock_resend.Emails.send.call_args[0][0]
        self.assertEqual(call_kwargs["from"], "noreply@app.example.com")
        self.assertEqual(call_kwargs["to"], "user@example.com")
        self.assertEqual(call_kwargs["subject"], "Verify Your Email")
        self.assertIn("verify-email?token=", call_kwargs["html"])

    @override_settings(RESEND_API_KEY="re_test_key", FRONTEND_URL="https://app.example.com")
    def test_logs_and_reraises_exception_when_resend_fails(self):
        mock_resend = MagicMock()
        mock_resend.Emails.send.side_effect = Exception("API down")

        with patch.dict(sys.modules, {"resend": mock_resend}):
            with self.assertLogs("authentication.services", level="ERROR") as log:
                with self.assertRaises(Exception, msg="API down"):
                    send_verification_email("user@example.com")

        self.assertTrue(any("Failed to send" in msg for msg in log.output))

    @override_settings(RESEND_API_KEY="", FRONTEND_URL="https://myapp.com")
    @patch("builtins.print")
    def test_uses_frontend_url_setting(self, mock_print):
        send_verification_email("user@example.com")

        printed_text = mock_print.call_args[0][0]
        self.assertIn("https://myapp.com/auth/verify-email?token=", printed_text)

class GenerateTokensTest(SimpleTestCase):
    SECRET_KEY = "test-secret-key"

    def setUp(self):
        self.user_id = uuid.uuid4()
        self.email = "user@example.com"
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            self.tokens = generate_tokens(self.user_id, self.email)

    def _decode(self, token):
        return jwt.decode(token, self.SECRET_KEY, algorithms=["HS256"])

    def test_returns_access_and_refresh_token_keys(self):
        self.assertIn("access_token", self.tokens)
        self.assertIn("refresh_token", self.tokens)

    def test_access_token_payload(self):
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            payload = self._decode(self.tokens["access_token"])
        self.assertEqual(payload["user_id"], str(self.user_id))
        self.assertEqual(payload["email"], self.email)
        self.assertEqual(payload["type"], "access")

    def test_refresh_token_payload(self):
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            payload = self._decode(self.tokens["refresh_token"])
        self.assertEqual(payload["user_id"], str(self.user_id))
        self.assertEqual(payload["email"], self.email)
        self.assertEqual(payload["type"], "refresh")

    def test_access_token_expiry_is_approximately_one_hour(self):
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            payload = self._decode(self.tokens["access_token"])
        delta = payload["exp"] - payload["iat"]
        self.assertAlmostEqual(delta, 3600, delta=5)

    def test_refresh_token_expiry_is_approximately_seven_days(self):
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            payload = self._decode(self.tokens["refresh_token"])
        delta = payload["exp"] - payload["iat"]
        self.assertAlmostEqual(delta, 7 * 86400, delta=5)

    def test_different_users_produce_different_tokens(self):
        other_id = uuid.uuid4()
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            other_tokens = generate_tokens(other_id, "other@example.com")
        self.assertNotEqual(self.tokens["access_token"], other_tokens["access_token"])
        self.assertNotEqual(self.tokens["refresh_token"], other_tokens["refresh_token"])

    def test_expired_access_token_raises_error(self):
        from datetime import timedelta
        past = int((timezone.now() - timedelta(hours=2)).timestamp())
        expired_payload = {
            "user_id": str(self.user_id),
            "email": self.email,
            "type": "access",
            "iat": past,
            "exp": past + 3600,
        }
        expired_token = jwt.encode(expired_payload, self.SECRET_KEY, algorithm="HS256")
        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, self.SECRET_KEY, algorithms=["HS256"])
