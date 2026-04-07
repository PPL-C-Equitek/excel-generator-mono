import sys
import jwt
import uuid
from unittest.mock import patch, MagicMock
from django.utils import timezone

from django.core.signing import TimestampSigner
from django.test import SimpleTestCase, override_settings
from authentication.models import User
from authentication.services import RefreshTokenService, generate_verification_token, send_verification_email, generate_tokens, DjangoUserLookupGateway, LoginFailureTracker, InvalidRefreshTokenError

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
    def test_logs_verification_link_when_no_api_key(self):
        with self.assertLogs("authentication.services", level="INFO") as log:
            send_verification_email("user@example.com")

        log_text = "\n".join(log.output)
        self.assertIn("Verification link", log_text)
        self.assertIn("verify-email?token=", log_text)

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
    def test_uses_frontend_url_setting(self):
        with self.assertLogs("authentication.services", level="INFO") as log:
            send_verification_email("user@example.com")

        log_text = "\n".join(log.output)
        self.assertIn("https://myapp.com/auth/verify-email?token=", log_text)

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

class DjangoUserLookupGatewayTest(SimpleTestCase):
    def test_get_by_email_returns_user(self):
        mock_user = MagicMock(spec=User)
        with patch("authentication.models.User.objects.get", return_value=mock_user) as mock_get:
            gateway = DjangoUserLookupGateway()
            result = gateway.get_by_email("user@example.com")

        mock_get.assert_called_once_with(email="user@example.com")
        self.assertEqual(result, mock_user)

class GenerateTokensMissingSecretKeyTest(SimpleTestCase):
    def test_raises_value_error_when_jwt_secret_key_not_configured(self):
        with self.settings(JWT_SECRET_KEY=None):
            with self.assertRaises(ValueError, msg="JWT_SECRET_KEY is not configured"):
                generate_tokens(uuid.uuid4(), "user@example.com")

class LoginFailureTrackerCacheBackendTest(SimpleTestCase):
    def test_get_cache_backend_returns_cache(self):
        from django.core.cache import cache
        result = LoginFailureTracker.get_cache_backend()
        self.assertIs(result, cache)

class RefreshTokenServiceTest(SimpleTestCase):
    SECRET_KEY = "test-secret-key"

    def _make_refresh_token(self, payload_override=None):
        """Helper: buat refresh token valid dengan override payload opsional."""
        now = int(timezone.now().timestamp())
        payload = {
            "user_id": str(uuid.uuid4()),
            "email": "user@example.com",
            "type": "refresh",
            "iat": now,
            "exp": now + 7 * 86400,
        }
        if payload_override:
            payload.update(payload_override)
        return jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")

    def test_raises_when_jwt_secret_key_not_configured(self):
        token = self._make_refresh_token()
        with self.settings(JWT_SECRET_KEY=""):
            with self.assertRaises(InvalidRefreshTokenError, msg="JWT secret is not configured."):
                RefreshTokenService().refresh(token)

    def test_raises_when_payload_missing_user_id(self):
        token = self._make_refresh_token({"user_id": ""})
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            with self.assertRaises(InvalidRefreshTokenError, msg="Invalid token payload."):
                RefreshTokenService().refresh(token)

    def test_raises_when_payload_missing_email(self):
        token = self._make_refresh_token({"email": ""})
        with self.settings(JWT_SECRET_KEY=self.SECRET_KEY):
            with self.assertRaises(InvalidRefreshTokenError, msg="Invalid token payload."):
                RefreshTokenService().refresh(token)
