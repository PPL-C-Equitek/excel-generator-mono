import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from authentication.oauth_services import GoogleOAuthService

GOOGLE_OAUTH_URL = "/auth/google-oauth/"
MOCK_CLIENT_ID = "mock-google-client-id"
MOCK_ID_TOKEN = "header.payload.signature"
MOCK_ACCESS_TOKEN = "ya29.mock-access-token"


class GoogleOAuthServiceTest(TestCase):
    def setUp(self):
        self.service = GoogleOAuthService(google_client_id=MOCK_CLIENT_ID)

    # Positive
    @patch("authentication.oauth_services.urlopen")
    def test_fetch_json_returns_parsed_payload(self, mock_urlopen):
        """Should return parsed JSON when upstream response is valid"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"aud":"mock-google-client-id"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        data = self.service._fetch_json("https://example.com/tokeninfo")

        self.assertEqual(data["aud"], MOCK_CLIENT_ID)

    @patch("authentication.oauth_services.id_token.verify_oauth2_token")
    def test_verify_id_token_maps_fields(self, mock_verify):
        """Should map Google ID token payload correctly"""
        mock_verify.return_value = {
            "email": "user1@gmail.com",
            "name": "User 1",
            "picture": "https://image.example/u1.jpg",
        }

        payload = self.service._verify_id_token(MOCK_ID_TOKEN)

        self.assertEqual(payload["email"], "user1@gmail.com")
        self.assertEqual(payload["name"], "User 1")

    @patch.object(GoogleOAuthService, "_fetch_json")
    def test_verify_access_token_returns_userinfo_when_audience_matches(self, mock_fetch_json):
        """Should return user info when audience matches client ID"""
        mock_fetch_json.side_effect = [
            {"aud": MOCK_CLIENT_ID, "azp": "some-other-client"},
            {"email": "user1@gmail.com", "name": "User 1", "picture": "https://example.com/pic.jpg"},
        ]

        payload = self.service._verify_access_token(MOCK_ACCESS_TOKEN)

        self.assertEqual(payload["email"], "user1@gmail.com")
        self.assertEqual(payload["name"], "User 1")
        self.assertEqual(mock_fetch_json.call_count, 2)

    @patch("authentication.oauth_services.generate_tokens")
    @patch.object(GoogleOAuthService, "verify_token")
    def test_authenticate_or_create_user_creates_verified_user_when_missing(
        self, mock_verify_token, mock_generate_tokens
    ):
        """Should create new verified user when user does not exist"""
        mock_verify_token.return_value = {
            "email": "new-user@gmail.com",
            "name": "  New User  ",
            "picture": "https://example.com/photo.jpg",
        }
        mock_generate_tokens.return_value = {
            "access_token": "app-access",
            "refresh_token": "app-refresh",
        }

        result = self.service.authenticate_or_create_user(MOCK_ACCESS_TOKEN)

        created_user = User.objects.get(email="new-user@gmail.com")
        self.assertEqual(created_user.name, "New User")
        self.assertEqual(created_user.status, "verified")
        self.assertEqual(result["tokens"]["access_token"], "app-access")


    # Negative
    @patch("authentication.oauth_services.urlopen", side_effect=URLError("timeout"))
    def test_fetch_json_raises_value_error_when_upstream_fails(self, _mock_urlopen):
        """Should raise ValueError when external request fails"""
        with self.assertRaises(ValueError, msg="Invalid Google token"):
            self.service._fetch_json("https://example.com/tokeninfo")

    @patch.object(GoogleOAuthService, "_fetch_json", return_value={"aud": "other", "azp": "other"})
    def test_verify_access_token_rejects_audience_mismatch(self, _mock_fetch_json):
        """Should reject token when audience does not match"""
        with self.assertRaises(ValueError, msg="Google token audience mismatch"):
            self.service._verify_access_token(MOCK_ACCESS_TOKEN)

    @patch.object(GoogleOAuthService, "_fetch_json")
    def test_verify_access_token_rejects_missing_email(self, mock_fetch_json):
        """Should reject token when email is missing from user info"""
        mock_fetch_json.side_effect = [{"aud": MOCK_CLIENT_ID}, {"name": "No Email"}]

        with self.assertRaises(ValueError, msg="Google account email not available"):
            self.service._verify_access_token(MOCK_ACCESS_TOKEN)

    @patch.object(GoogleOAuthService, "_verify_access_token", side_effect=ValueError("boom"))
    def test_verify_token_wraps_value_error(self, _mock_access):
        """Should normalize internal errors into generic ValueError"""
        with self.assertRaises(ValueError, msg="Invalid Google token"):
            self.service.verify_token("ya29.invalid")


    # Edge Case
    @patch.object(GoogleOAuthService, "_fetch_json")
    def test_verify_access_token_accepts_authorized_party_match(self, mock_fetch_json):
        """Should accept token when azp matches client ID (special Google case)"""
        mock_fetch_json.side_effect = [
            {"aud": "other-client", "azp": MOCK_CLIENT_ID},
            {"email": "user1@gmail.com", "name": "User 1"},
        ]

        payload = self.service._verify_access_token(MOCK_ACCESS_TOKEN)

        self.assertEqual(payload["email"], "user1@gmail.com")

    @patch.object(GoogleOAuthService, "_verify_id_token", return_value={"email": "id@example.com"})
    @patch.object(GoogleOAuthService, "_verify_access_token", return_value={"email": "access@example.com"})
    def test_verify_token_uses_id_token_path_for_jwt(self, mock_access, mock_id):
        """Should use ID token verification when token is JWT format"""
        result = self.service.verify_token("a.b.c")

        self.assertEqual(result["email"], "id@example.com")
        mock_id.assert_called_once()
        mock_access.assert_not_called()

    @patch.object(GoogleOAuthService, "_verify_id_token", return_value={"email": "id@example.com"})
    @patch.object(GoogleOAuthService, "_verify_access_token", return_value={"email": "access@example.com"})
    def test_verify_token_uses_access_token_path_for_non_jwt(self, mock_access, mock_id):
        """Should use access token verification when token is not JWT"""
        result = self.service.verify_token("ya29.token")

        self.assertEqual(result["email"], "access@example.com")
        mock_access.assert_called_once()
        mock_id.assert_not_called()

    @patch("authentication.oauth_services.generate_tokens")
    @patch.object(GoogleOAuthService, "verify_token")
    def test_authenticate_or_create_user_fallbacks_name_to_email_prefix_when_blank(
        self, mock_verify_token, mock_generate_tokens
    ):
        """Should fallback to email prefix when name is blank"""
        mock_verify_token.return_value = {
            "email": "fallback-user@gmail.com",
            "name": "   ",
        }

        self.service.authenticate_or_create_user(MOCK_ACCESS_TOKEN)

        created_user = User.objects.get(email="fallback-user@gmail.com")
        self.assertEqual(created_user.name, "fallback-user")

    @patch("authentication.oauth_services.generate_tokens")
    @patch.object(GoogleOAuthService, "verify_token")
    def test_authenticate_or_create_user_updates_existing_user_name_and_status(
        self, mock_verify_token, mock_generate_tokens
    ):
        """Should update existing user when data is outdated"""
        existing = User.objects.create(
            email="existing@gmail.com",
            name="Old Name",
            password="",
            status="unverified",
        )

        mock_verify_token.return_value = {
            "email": "existing@gmail.com",
            "name": "New Name",
        }

        self.service.authenticate_or_create_user(MOCK_ACCESS_TOKEN)

        existing.refresh_from_db()
        self.assertEqual(existing.name, "New Name")
        self.assertEqual(existing.status, "verified")

    @patch("authentication.oauth_services.generate_tokens")
    @patch.object(GoogleOAuthService, "verify_token")
    def test_authenticate_or_create_user_keeps_existing_values_when_already_synced(
        self, mock_verify_token, mock_generate_tokens
    ):
        """Should not update user when data is already in sync"""
        existing = User.objects.create(
            email="sync@gmail.com",
            name="Sync User",
            password="",
            status="verified",
        )

        mock_verify_token.return_value = {
            "email": "sync@gmail.com",
            "name": "Sync User",
        }

        self.service.authenticate_or_create_user(MOCK_ACCESS_TOKEN)

        existing.refresh_from_db()
        self.assertEqual(existing.name, "Sync User")
        self.assertEqual(existing.status, "verified")

class GoogleOAuthCallbackViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    # Positive
    @override_settings(GOOGLE_OAUTH_CLIENT_ID=MOCK_CLIENT_ID)
    @patch("authentication.views.GoogleOAuthService")
    def test_returns_tokens_and_user_on_success(self, mock_service_class):
        """Should return tokens and user data when authentication succeeds"""
        service = MagicMock()
        service.authenticate_or_create_user.return_value = {
            "user": SimpleNamespace(id=1, email="user1@gmail.com", name="User 1"),
            "tokens": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
            },
        }
        mock_service_class.return_value = service

        response = self.client.post(
            GOOGLE_OAUTH_URL,
            {"token": MOCK_ACCESS_TOKEN},
            format="json",
            secure=True,
        )
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["access_token"], "mock-access-token")
        self.assertEqual(payload["refresh_token"], "mock-refresh-token")
        self.assertEqual(payload["user"]["email"], "user1@gmail.com")
        mock_service_class.assert_called_once_with(MOCK_CLIENT_ID)


    # Negative
    @override_settings(DEBUG=False)
    def test_returns_400_when_request_is_not_https_in_production(self):
        """Should reject non-HTTPS request when DEBUG is disabled"""
        response = self.client.post(GOOGLE_OAUTH_URL, {"token": MOCK_ACCESS_TOKEN}, format="json")
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(payload.get("message"), "HTTPS required")

    @override_settings(DEBUG=True)
    def test_returns_400_when_token_missing(self):
        """Should return 400 when token is not provided"""
        response = self.client.post(GOOGLE_OAUTH_URL, {}, format="json")
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", payload)

    @override_settings(DEBUG=True)
    def test_returns_400_when_token_is_empty(self):
        """Should return 400 when token is empty string"""
        response = self.client.post(GOOGLE_OAUTH_URL, {"token": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_get_requests(self):
        """Should reject safe HTTP methods that are not explicitly allowed"""
        response = self.client.get(GOOGLE_OAUTH_URL)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_rejects_put_requests(self):
        """Should reject unsafe HTTP methods other than POST"""
        response = self.client.put(GOOGLE_OAUTH_URL, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID=MOCK_CLIENT_ID)
    @patch("authentication.views.GoogleOAuthService")
    def test_returns_401_when_service_raises_value_error(self, mock_service_class):
        """Should return 401 when service raises ValueError (invalid token)"""
        service = MagicMock()
        service.authenticate_or_create_user.side_effect = ValueError("Invalid token")
        mock_service_class.return_value = service

        response = self.client.post(
            GOOGLE_OAUTH_URL,
            {"token": "header.payload.signature"},
            format="json",
            secure=True,
        )
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", payload)


    # Edge Case
    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_returns_500_when_google_client_id_missing(self):
        """Should return 500 when server config (client ID) is missing"""
        response = self.client.post(
            GOOGLE_OAUTH_URL,
            {"token": MOCK_ID_TOKEN},
            format="json",
            secure=True,
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID=MOCK_CLIENT_ID)
    @patch("authentication.views.GoogleOAuthService")
    def test_returns_500_on_unexpected_exception(self, mock_service_class):
        """Should return 500 and hide internal error details on unexpected exception"""
        service = MagicMock()
        service.authenticate_or_create_user.side_effect = RuntimeError("database unavailable")
        mock_service_class.return_value = service

        response = self.client.post(
            GOOGLE_OAUTH_URL,
            {"token": MOCK_ID_TOKEN},
            format="json",
            secure=True,
        )
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("database unavailable", json.dumps(payload))