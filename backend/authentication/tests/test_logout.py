import hashlib
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

import jwt
from django.conf import settings
from django.utils import timezone
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.logout.adapters import DjangoTokenBlacklistRepository
from authentication.models import User
from authentication.services import generate_tokens
from authentication.views import blacklist_refresh_token


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
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]

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
        mock_blacklist_refresh_token.side_effect = [None, ValueError("Token already blacklisted")]

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

    def test_logout_with_missing_refresh_token_returns_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "refresh_token is required")

    def test_logout_with_empty_refresh_token_returns_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            self.url,
            {"refresh_token": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "refresh_token is required")

    def test_logout_with_non_string_refresh_token_returns_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        response = self.client.post(
            self.url,
            {"refresh_token": 12345},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "refresh_token is required")

    @patch("authentication.views.blacklist_refresh_token", create=True)
    def test_logout_with_unexpected_error_returns_500(self, mock_blacklist_refresh_token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        self.client.raise_request_exception = False
        mock_blacklist_refresh_token.side_effect = RuntimeError("unexpected failure")

        response = self.client.post(
            self.url,
            {"refresh_token": self.refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


@override_settings(JWT_SECRET_KEY="test-jwt-secret-key-with-at-least-32-bytes")
class DjangoTokenBlacklistRepositoryTest(APITestCase):
    def setUp(self):
        self.repo = DjangoTokenBlacklistRepository()
        self.refresh_token = "refresh.token.value"

    @patch("authentication.logout.adapters.cache.add")
    @patch("authentication.logout.adapters.timezone.now")
    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_uses_hashed_key_atomic_add_and_dynamic_timeout(
        self,
        mock_jwt_decode,
        mock_timezone_now,
        mock_cache_add,
    ):
        fixed_now = datetime(2026, 4, 5, 12, 0, 0, tzinfo=dt_timezone.utc)
        mock_timezone_now.return_value = fixed_now
        exp_ts = int(fixed_now.timestamp()) + 120
        mock_jwt_decode.return_value = {"type": "refresh", "exp": exp_ts}
        mock_cache_add.return_value = True

        self.repo.blacklist(self.refresh_token)

        expected_hash = hashlib.sha256(self.refresh_token.encode()).hexdigest()
        mock_cache_add.assert_called_once_with(
            f"blacklisted_refresh_token:{expected_hash}",
            True,
            timeout=120,
        )

    @patch("authentication.logout.adapters.cache.add")
    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_uses_default_timeout_when_exp_missing(
        self,
        mock_jwt_decode,
        mock_cache_add,
    ):
        mock_jwt_decode.return_value = {"type": "refresh"}
        mock_cache_add.return_value = True

        self.repo.blacklist(self.refresh_token)

        expected_hash = hashlib.sha256(self.refresh_token.encode()).hexdigest()
        mock_cache_add.assert_called_once_with(
            f"blacklisted_refresh_token:{expected_hash}",
            True,
            timeout=7 * 24 * 60 * 60,
        )

    @patch("authentication.logout.adapters.cache.add")
    @patch("authentication.logout.adapters.timezone.now")
    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_uses_minimum_timeout_of_one_second_when_expired(
        self,
        mock_jwt_decode,
        mock_timezone_now,
        mock_cache_add,
    ):
        fixed_now = datetime(2026, 4, 5, 12, 0, 0, tzinfo=dt_timezone.utc)
        mock_timezone_now.return_value = fixed_now
        exp_ts = int(fixed_now.timestamp()) - 10
        mock_jwt_decode.return_value = {"type": "refresh", "exp": exp_ts}
        mock_cache_add.return_value = True

        self.repo.blacklist(self.refresh_token)

        expected_hash = hashlib.sha256(self.refresh_token.encode()).hexdigest()
        mock_cache_add.assert_called_once_with(
            f"blacklisted_refresh_token:{expected_hash}",
            True,
            timeout=1,
        )

    @patch("authentication.logout.adapters.cache.add")
    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_raises_when_token_already_blacklisted(
        self,
        mock_jwt_decode,
        mock_cache_add,
    ):
        mock_jwt_decode.return_value = {"type": "refresh", "exp": int(timezone.now().timestamp()) + 60}
        mock_cache_add.return_value = False

        with self.assertRaises(ValueError) as ctx:
            self.repo.blacklist(self.refresh_token)

        self.assertEqual(str(ctx.exception), "Token already blacklisted")

    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_raises_for_invalid_refresh_token(self, mock_jwt_decode):
        mock_jwt_decode.side_effect = jwt.InvalidTokenError("bad token")

        with self.assertRaises(ValueError) as ctx:
            self.repo.blacklist(self.refresh_token)

        self.assertEqual(str(ctx.exception), "Invalid refresh token")

    @patch("authentication.logout.adapters.jwt.decode")
    def test_blacklist_raises_for_wrong_token_type(self, mock_jwt_decode):
        mock_jwt_decode.return_value = {"type": "access", "exp": int(timezone.now().timestamp()) + 60}

        with self.assertRaises(ValueError) as ctx:
            self.repo.blacklist(self.refresh_token)

        self.assertEqual(str(ctx.exception), "Invalid token type")

    def test_blacklist_raises_when_refresh_token_empty(self):
        with self.assertRaises(ValueError) as ctx:
            self.repo.blacklist("")

        self.assertEqual(str(ctx.exception), "Refresh token is required")


class LogoutViewCompatibilityHelperTest(APITestCase):
    @patch("authentication.views.DjangoTokenBlacklistRepository")
    def test_blacklist_refresh_token_delegates_to_django_repository(self, mock_repo_cls):
        mock_repo = mock_repo_cls.return_value

        blacklist_refresh_token("refresh-token")

        mock_repo.blacklist.assert_called_once_with("refresh-token")
