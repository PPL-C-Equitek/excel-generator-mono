import uuid
from datetime import timedelta

import jwt
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework import status

from authentication.services import generate_tokens


SECRET_KEY = "test-secret-key-12345678901234567890"


class RefreshTokenViewTest(SimpleTestCase):
    def setUp(self):
        self.url = "/auth/refresh/"
        self.user_id = uuid.uuid4()
        self.email = "user@example.com"

    def _refresh_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            return generate_tokens(self.user_id, self.email)["refreshToken"]

    def _access_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            return generate_tokens(self.user_id, self.email)["accessToken"]

    def test_refresh_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_refresh_valid_token_returns_200(self):
        refresh_token = self._refresh_token()
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refreshToken": refresh_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("accessToken", response.data)
        self.assertIn("refreshToken", response.data)

        access_payload = jwt.decode(
            response.data["accessToken"],
            SECRET_KEY,
            algorithms=["HS256"],
        )
        refresh_payload = jwt.decode(
            response.data["refreshToken"],
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
                {"refreshToken": access_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)
        self.assertIn("tidak valid", response.data["message"].lower())

    def test_refresh_rejects_invalid_token(self):
        with override_settings(JWT_SECRET_KEY=SECRET_KEY):
            response = self.client.post(
                self.url,
                {"refreshToken": "invalid.token.value"},
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
                {"refreshToken": expired_token},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expired", response.data["message"].lower())
