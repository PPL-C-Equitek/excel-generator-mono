import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import jwt
from django.utils import timezone
from django.test import SimpleTestCase
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from authentication.jwt_authentication import JWTAuthentication
from authentication.models import User


class JWTAuthenticationTest(SimpleTestCase):
    SECRET_KEY = "test-secret-key"

    def setUp(self):
        self.auth = JWTAuthentication()
        self.factory = APIRequestFactory()

    def _request_with_header(self, header_value):
        return self.factory.get("/api/health/", HTTP_AUTHORIZATION=header_value)

    def _access_token(self, user_id):
        now = timezone.now()
        payload = {
            "user_id": str(user_id),
            "email": "user@example.com",
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")

    @patch("authentication.jwt_authentication.User")
    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_returns_none_when_no_authorization_header(self, mock_settings, mock_user_model):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY

        request = self.factory.get("/api/health/")
        result = self.auth.authenticate(request)

        self.assertIsNone(result)
        mock_user_model.objects.select_related.assert_not_called()

    @patch("authentication.jwt_authentication.User")
    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_returns_none_for_non_bearer_header(self, mock_settings, mock_user_model):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY

        request = self._request_with_header("Token abc.def.ghi")
        result = self.auth.authenticate(request)

        self.assertIsNone(result)
        mock_user_model.objects.select_related.assert_not_called()

    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_raises_when_jwt_secret_not_configured(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = ""

        request = self._request_with_header("Bearer any.token")

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("JWT secret is not configured", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_raises_for_invalid_token(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY

        request = self._request_with_header("Bearer invalid.token")

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("Invalid token", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_raises_for_expired_token(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY
        past = timezone.now() - timedelta(hours=2)
        payload = {
            "user_id": str(uuid.uuid4()),
            "email": "user@example.com",
            "type": "access",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
        }
        expired_token = jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")
        request = self._request_with_header(f"Bearer {expired_token}")

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("Token has expired", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_raises_for_non_access_token_type(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY
        now = timezone.now()
        payload = {
            "user_id": str(uuid.uuid4()),
            "email": "user@example.com",
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        }
        token = jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")
        request = self._request_with_header(f"Bearer {token}")

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("Invalid token type", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    def test_authenticate_raises_when_user_id_missing(self, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY
        now = timezone.now()
        payload = {
            "email": "user@example.com",
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        }
        token = jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")
        request = self._request_with_header(f"Bearer {token}")

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("Invalid token payload", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    @patch("authentication.jwt_authentication.User")
    def test_authenticate_raises_when_user_not_found(self, mock_user_model, mock_settings):
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY
        token = self._access_token(uuid.uuid4())
        request = self._request_with_header(f"Bearer {token}")

        mock_user_model.DoesNotExist = User.DoesNotExist
        query = mock_user_model.objects.select_related.return_value
        query.get.side_effect = User.DoesNotExist()

        with self.assertRaises(exceptions.AuthenticationFailed) as exc:
            self.auth.authenticate(request)

        self.assertIn("User not found", str(exc.exception))

    @patch("authentication.jwt_authentication.settings")
    @patch("authentication.jwt_authentication.User")
    def test_authenticate_returns_user_and_payload_when_valid(self, mock_user_model, mock_settings):
        user_id = uuid.uuid4()
        mock_settings.JWT_SECRET_KEY = self.SECRET_KEY
        token = self._access_token(user_id)
        request = self._request_with_header(f"Bearer {token}")

        expected_user = MagicMock()
        query = mock_user_model.objects.select_related.return_value
        query.get.return_value = expected_user

        user, payload = self.auth.authenticate(request)

        self.assertIs(user, expected_user)
        self.assertEqual(payload["user_id"], str(user_id))
        self.assertEqual(payload["type"], "access")
        mock_user_model.objects.select_related.assert_called_once_with("monitoring_account")
        query.get.assert_called_once_with(id=str(user_id))
