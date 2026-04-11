from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.logout.adapters import DjangoTokenBlacklistRepository
from authentication.models import User
from authentication.services import generate_tokens


@override_settings(JWT_SECRET_KEY="test-jwt-secret-key-with-at-least-32-bytes")
class ChangePasswordViewTest(APITestCase):
    def setUp(self):
        self.url = "/auth/change-password/"
        self.user = User.objects.create_user(
            email="change.password@example.com",
            name="Change Password User",
            password="Current#123",
            status="verified",
        )
        tokens = generate_tokens(self.user.id, self.user.email)
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_changes_password_for_authenticated_user(self, mock_send_email):
        response = self.client.post(
            self.url,
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
                "refresh_token": self.refresh_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Password changed successfully.",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Updated#123"))
        mock_send_email.assert_called_once_with(self.user.email)
        self.assertTrue(
            DjangoTokenBlacklistRepository().is_blacklisted(self.refresh_token)
        )

    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_missing_current_password_returns_400_for_user_with_password(
        self, mock_send_email
    ):
        response = self.client.post(
            self.url,
            {
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            "Current password is required.",
        )
        mock_send_email.assert_not_called()

    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_wrong_current_password_returns_400(self, mock_send_email):
        response = self.client.post(
            self.url,
            {
                "current_password": "Wrong#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            "Current password is incorrect.",
        )
        mock_send_email.assert_not_called()

    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_same_password_returns_400(self, mock_send_email):
        response = self.client.post(
            self.url,
            {
                "current_password": "Current#123",
                "new_password": "Current#123",
                "new_password_confirm": "Current#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["message"],
            "New password must be different from the current password.",
        )
        mock_send_email.assert_not_called()

    def test_password_confirmation_mismatch_returns_400(self):
        response = self.client.post(
            self.url,
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#124",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_unauthenticated_user_returns_401(self):
        self.client.credentials()

        response = self.client.post(
            self.url,
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_google_only_user_can_set_password_without_current_password(
        self, mock_send_email
    ):
        google_user = User.objects.create_user(
            email="google.only@example.com",
            name="Google Only",
            status="verified",
        )
        google_user.set_unusable_password()
        google_user.save(update_fields=["password"])
        tokens = generate_tokens(google_user.id, google_user.email)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}"
        )

        response = self.client.post(
            self.url,
            {
                "current_password": "",
                "new_password": "NewGoogle#123",
                "new_password_confirm": "NewGoogle#123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        google_user.refresh_from_db()
        self.assertTrue(google_user.check_password("NewGoogle#123"))
        mock_send_email.assert_called_once_with("google.only@example.com")

    @patch(
        "authentication.change_password.adapters.DjangoTokenBlacklistRepository.blacklist"
    )
    @patch("authentication.change_password.adapters.send_password_changed_email")
    def test_invalid_refresh_token_does_not_fail_password_change(
        self,
        mock_send_email,
        mock_blacklist,
    ):
        mock_blacklist.side_effect = ValueError("Invalid refresh token")

        response = self.client.post(
            self.url,
            {
                "current_password": "Current#123",
                "new_password": "Updated#123",
                "new_password_confirm": "Updated#123",
                "refresh_token": "bad-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Updated#123"))
        mock_send_email.assert_called_once_with(self.user.email)
