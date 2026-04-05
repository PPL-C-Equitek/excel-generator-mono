from datetime import timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.utils import timezone
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services import generate_tokens


@override_settings(JWT_SECRET_KEY="test-jwt-secret-key-with-at-least-32-bytes")
class LogoutViewTest(APITestCase):
    def setUp(self):
        self.url = "/auth/logout/"
        self.user = User.objects.create_user(
            email="logout.user@example.com",
            name="Logout User",
            password="securePass1",
            status="verified",
        )

        tokens = generate_tokens(self.user.id, self.user.email)
        self.access_token = tokens["accessToken"]
        self.refresh_token = tokens["refreshToken"]

    @patch("authentication.views.blacklist_refresh_token", create=True)
    def test_logout_with_valid_auth_and_refresh_token_returns_success_and_blacklists_token(
        self, mock_blacklist_refresh_token
    ):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
        )
        mock_blacklist_refresh_token.assert_called_once_with(self.refresh_token)

    def test_logout_without_auth_token_returns_401_unauthorized(self):
        response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("authentication.views.blacklist_refresh_token", create=True)
    def test_double_logout_second_request_with_same_token_returns_401(
        self, mock_blacklist_refresh_token
    ):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        mock_blacklist_refresh_token.side_effect = [None, Exception("Token already blacklisted")]

        first_response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )
        second_response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )

        self.assertIn(
            first_response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
        )
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(mock_blacklist_refresh_token.call_count, 2)

    @patch("authentication.views.blacklist_refresh_token", create=True)
    def test_logout_with_expired_access_token_returns_401_before_blacklist_logic(
        self, mock_blacklist_refresh_token
    ):
        now = timezone.now()
        expired_access_payload = {
            "user_id": str(self.user.id),
            "email": self.user.email,
            "type": "access",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "iss": "excel-generator",
        }
        expired_access_token = jwt.encode(
            expired_access_payload,
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_access_token}")

        response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_blacklist_refresh_token.assert_not_called()
