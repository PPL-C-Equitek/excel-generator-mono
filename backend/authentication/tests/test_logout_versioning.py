from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services import generate_tokens


@override_settings(JWT_SECRET_KEY="test-jwt-secret-key-with-at-least-32-bytes")
class LogoutTokenVersioningTest(APITestCase):
    def setUp(self):
        self.protected_url = "/history/"
        self.logout_url = "/auth/logout/"

        self.user = User.objects.create_user(
            email="versioning.user@example.com",
            name="Versioning User",
            password="Secure#123",
            status="verified",
        )

        tokens = generate_tokens(self.user.id, self.user.email)
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]

    def test_access_token_is_rejected_after_logout_when_session_version_changes(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        protected_before_logout = self.client.get(self.protected_url)
        self.assertEqual(protected_before_logout.status_code, status.HTTP_200_OK)

        logout_response = self.client.post(
            self.logout_url,
            {"refresh_token": self.refresh_token},
            format="json",
        )
        self.assertIn(
            logout_response.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
        )

        protected_after_logout = self.client.get(self.protected_url)
        self.assertEqual(
            protected_after_logout.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
