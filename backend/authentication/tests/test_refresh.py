import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status

from authentication.logout.adapters import DjangoTokenBlacklistRepository
from authentication.models import User
from authentication.services import generate_tokens


SECRET_KEY = "test-secret-key-12345678901234567890"


class RefreshTokenViewTest(TestCase):
    def setUp(self):
        self.url = "/auth/refresh/"
        self.user_id = uuid.uuid4()
        self.email = "user@example.com"
        self.user = User.objects.create(
            id=self.user_id,
            email=self.email,
            name="Refresh User",
            password="",
            status="verified",
        )

    def _refresh_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            return generate_tokens(self.user_id, self.email)["refresh_token"]

    def _access_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            return generate_tokens(self.user_id, self.email)["access_token"]

    def test_refresh_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_refresh_valid_token_returns_200(self):
        refresh_token = self._refresh_token()
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": refresh_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)

        access_payload = jwt.decode(
            response.data["access_token"],
            SECRET_KEY,
            algorithms=["HS256"],
        )
        refresh_payload = jwt.decode(
            response.data["refresh_token"],
            SECRET_KEY,
            algorithms=["HS256"],
        )

        self.assertEqual(access_payload["type"], "access")
        self.assertEqual(refresh_payload["type"], "refresh")
        self.assertEqual(access_payload["user_id"], str(self.user_id))
        self.assertEqual(refresh_payload["user_id"], str(self.user_id))
        self.assertEqual(access_payload["email"], self.email)
        self.assertEqual(refresh_payload["email"], self.email)

    def test_refresh_rejects_access_token(self):
        access_token = self._access_token()
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": access_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)
        self.assertIn("tidak valid", response.data["message"].lower())

    def test_refresh_rejects_invalid_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": "invalid.token.value"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)

    def test_refresh_rejects_expired_token(self):
        past = timezone.now() - timedelta(hours=2)
        payload = {
            "user_id": str(self.user_id),
            "email": self.email,
            "type": "refresh",
            "iat": int(past.timestamp()),
            "exp": int((past + timedelta(minutes=1)).timestamp()),
        }
        expired_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": expired_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expired", response.data["message"].lower())

    def test_refresh_rejects_when_user_is_deleted(self):
        refresh_token = self._refresh_token()
        self.user.delete()

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": refresh_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)
        self.assertIn("tidak valid", response.data["message"].lower())

    def test_refresh_rejects_when_user_is_unverified(self):
        refresh_token = self._refresh_token()
        self.user.status = "unverified"
        self.user.save(update_fields=["status"])

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": refresh_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)
        self.assertIn("tidak valid", response.data["message"].lower())

    def test_refresh_rejects_blacklisted_refresh_token(self):
        refresh_token = self._refresh_token()

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            DjangoTokenBlacklistRepository().blacklist(refresh_token)

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": refresh_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("logout", response.data["message"].lower())
        
    @patch("authentication.views.RefreshTokenService")
    def test_refresh_unexpected_error_returns_500(self, mock_service_class):
        mock_service_class.return_value.refresh.side_effect = Exception("Unexpected error")

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refresh_token": "any.token.value"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.data)

    @patch("authentication.views.RefreshTokenService")
    def test_refresh_unexpected_error_logs_exception(self, mock_service_class):
        mock_service_class.return_value.refresh.side_effect = Exception("DB failure")

        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            with self.assertLogs("authentication.views", level="ERROR") as log:
                self.client.post(
                    self.url,
                    {"refresh_token": "any.token.value"},
                    format="json",
                )

        self.assertTrue(
            any("Unexpected error during refresh token exchange" in msg for msg in log.output)
        )
