import uuid
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APISimpleTestCase


class LoginViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/login/"

    # Positive
    @patch("authentication.login.http.build_login_use_case")
    def test_login_valid_credentials_returns_200_with_tokens_and_user(self, mock_builder):
        from authentication.login.entities import AuthenticatedUser, LoginResult, TokenPair

        use_case = MagicMock()
        use_case.execute.return_value = LoginResult(
            tokens=TokenPair(access_token="access-token", refresh_token="refresh-token"),
            user=AuthenticatedUser(
                id=str(uuid.uuid4()),
                email="user@example.com",
                name="John Doe",
            ),
        )
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": " USER@Example.COM ", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["access_token"], "access-token")
        self.assertEqual(response.data["refresh_token"], "refresh-token")
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "user@example.com")
        self.assertNotIn("password", response.data["user"])

    @patch("monitoring.interfaces.http.decorators.get_monitoring_service")
    @patch("authentication.login.http.build_login_use_case")
    def test_login_records_auth_metric_event(self, mock_builder, mock_get_monitoring_service):
        from authentication.login.entities import AuthenticatedUser, LoginResult, TokenPair

        monitoring_service = MagicMock()
        mock_get_monitoring_service.return_value = monitoring_service

        use_case = MagicMock()
        use_case.execute.return_value = LoginResult(
            tokens=TokenPair(access_token="access-token", refresh_token="refresh-token"),
            user=AuthenticatedUser(
                id=str(uuid.uuid4()),
                email="user@example.com",
                name="John Doe",
            ),
        )
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        monitoring_service.record_event.assert_called_once_with(
            event_name="auth.login",
            outcome="success",
            endpoint="/auth/login/",
        )

    # Negative
    def test_login_missing_email_returns_400(self):
        response = self.client.post(
            self.url,
            {"password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_missing_password_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "user@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_invalid_email_format_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "invalid-email", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch("authentication.login.http.build_login_use_case")
    def test_login_invalid_credentials_returns_401(self, mock_builder):
        use_case = MagicMock()
        from authentication.login.exceptions import InvalidCredentialsError

        use_case.execute.side_effect = InvalidCredentialsError()
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["message"], "Invalid email or password.")

    @patch("authentication.login.http.build_login_use_case")
    def test_login_unverified_email_returns_403(self, mock_builder):
        use_case = MagicMock()
        from authentication.login.exceptions import EmailNotVerifiedError

        use_case.execute.side_effect = EmailNotVerifiedError()
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("check your inbox", response.data["message"].lower())

    @patch("authentication.login.http.build_login_use_case")
    def test_login_service_error_returns_500(self, mock_builder):
        use_case = MagicMock()
        from authentication.login.exceptions import LoginServiceError

        use_case.execute.side_effect = LoginServiceError("login failed")
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.data)

    # Edge Case
    @patch("authentication.login.http.build_login_use_case")
    def test_login_rate_limited_returns_429(self, mock_builder):
        use_case = MagicMock()
        from authentication.login.exceptions import LoginRateLimitedError

        use_case.execute.side_effect = LoginRateLimitedError()
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Too many failed attempts. Please try again in a few minutes.", response.data["message"])

    @patch("authentication.login.http.build_login_use_case")
    def test_login_unexpected_error_returns_500(self, mock_builder):
        use_case = MagicMock()
        use_case.execute.side_effect = RuntimeError("Database connection error")
        mock_builder.return_value = use_case

        response = self.client.post(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.data)

    def test_login_only_post_method_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.put(
            self.url,
            {"email": "user@example.com", "password": "securePass1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_login_invalid_json_returns_400(self):
        response = self.client.post(
            self.url,
            "{invalid json}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
