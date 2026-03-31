import sys
import json
from datetime import datetime, timezone
import uuid
from unittest.mock import patch, MagicMock

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
        self.assertEqual(call_kwargs["subject"], "Verifikasi Email Anda")
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

    @override_settings(FRONTEND_URL="https://myapp.com")
    @patch("builtins.print")
    def test_uses_frontend_url_setting(self, mock_print):
        send_verification_email("user@example.com")

        printed_text = mock_print.call_args[0][0]
        self.assertIn("https://myapp.com/auth/verify-email?token=", printed_text)

class GenerateTokensTest(SimpleTestCase):
    def setUp(self):
        self.user_id = uuid.uuid4()
        self.email = "user@example.com"
        self.tokens = generate_tokens(self.user_id, self.email)

    def test_returns_access_and_refresh_token_keys(self):
        self.assertIn("accessToken", self.tokens)
        self.assertIn("refreshToken", self.tokens)

    def test_access_token_is_unsignable(self):
        signer = TimestampSigner()
        raw = signer.unsign(self.tokens["accessToken"], max_age=60)
        payload = json.loads(raw)
        self.assertEqual(payload["user_id"], str(self.user_id))
        self.assertEqual(payload["email"], self.email)
        self.assertEqual(payload["type"], "access")

    def test_refresh_token_is_unsignable(self):
        signer = TimestampSigner()
        raw = signer.unsign(self.tokens["refreshToken"], max_age=60)
        payload = json.loads(raw)
        self.assertEqual(payload["user_id"], str(self.user_id))
        self.assertEqual(payload["email"], self.email)
        self.assertEqual(payload["type"], "refresh")

    def test_access_token_expiry_is_approximately_one_hour(self):
        signer = TimestampSigner()
        raw = signer.unsign(self.tokens["accessToken"], max_age=60)
        payload = json.loads(raw)
        exp = datetime.fromisoformat(payload["exp"])
        delta = exp - datetime.utcnow()
        # Toleransi ±5 detik dari 1 jam
        self.assertAlmostEqual(delta.total_seconds(), 3600, delta=5)

    def test_refresh_token_expiry_is_approximately_seven_days(self):
        signer = TimestampSigner()
        raw = signer.unsign(self.tokens["refreshToken"], max_age=60)
        payload = json.loads(raw)
        exp = datetime.fromisoformat(payload["exp"])
        delta = exp - datetime.utcnow()
        # Toleransi ±5 detik dari 7 hari
        self.assertAlmostEqual(delta.total_seconds(), 7 * 86400, delta=5)

    def test_different_users_produce_different_tokens(self):
        other_id = uuid.uuid4()
        other_tokens = generate_tokens(other_id, "other@example.com")
        self.assertNotEqual(self.tokens["accessToken"], other_tokens["accessToken"])
        self.assertNotEqual(self.tokens["refreshToken"], other_tokens["refreshToken"])