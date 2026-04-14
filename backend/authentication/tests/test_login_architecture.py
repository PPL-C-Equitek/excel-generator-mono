from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APISimpleTestCase, APIRequestFactory

from authentication.login.adapters import DjangoLoginFailureTracker
from authentication.login.entities import AuthenticatedUser, LoginCommand, LoginResult, TokenPair
from authentication.login.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    LoginRateLimitedError,
    LoginServiceError,
)
from authentication.login.http import LoginView
from authentication.login.use_cases import DefaultLoginUserUseCase
from authentication.models import User


class LoginCommandTest(APISimpleTestCase):
    def test_normalizes_email_for_consistent_lookup(self):
        command = LoginCommand(email="  User@Example.COM ", password="secret")

        self.assertEqual(command.email, "user@example.com")


class DefaultLoginUserUseCaseTest(APISimpleTestCase):
    def test_raises_rate_limited_when_tracker_blocks_email(self):
        lookup = MagicMock()
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = True
        token_generator = MagicMock()
        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        with self.assertRaises(LoginRateLimitedError):
            use_case.execute(LoginCommand(email="user@example.com", password="secret"))

        lookup.get_by_email.assert_not_called()
        token_generator.generate.assert_not_called()

    def test_raises_invalid_credentials_when_user_not_found(self):
        lookup = MagicMock()
        lookup.get_by_email.side_effect = User.DoesNotExist()
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = False
        token_generator = MagicMock()
        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        with self.assertRaises(InvalidCredentialsError):
            use_case.execute(LoginCommand(email="user@example.com", password="secret"))

        tracker.record_failure.assert_called_once_with("user@example.com")

    def test_raises_email_not_verified_for_unverified_user(self):
        user = MagicMock()
        user.status = "unverified"
        lookup = MagicMock()
        lookup.get_by_email.return_value = user
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = False
        token_generator = MagicMock()
        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        with self.assertRaises(EmailNotVerifiedError):
            use_case.execute(LoginCommand(email="user@example.com", password="secret"))

        tracker.record_failure.assert_called_once_with("user@example.com")

    def test_raises_invalid_credentials_for_wrong_password(self):
        user = MagicMock()
        user.status = "verified"
        user.check_password.return_value = False
        lookup = MagicMock()
        lookup.get_by_email.return_value = user
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = False
        token_generator = MagicMock()
        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        with self.assertRaises(InvalidCredentialsError):
            use_case.execute(LoginCommand(email="user@example.com", password="secret"))

        user.check_password.assert_called_once_with("secret")
        tracker.record_failure.assert_called_once_with("user@example.com")

    def test_returns_login_result_and_resets_failure_counter_on_success(self):
        user = MagicMock()
        user.id = "u-1"
        user.email = "user@example.com"
        user.name = "User"
        user.status = "verified"
        user.check_password.return_value = True

        lookup = MagicMock()
        lookup.get_by_email.return_value = user
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = False
        token_generator = MagicMock()
        token_generator.generate.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
        }

        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        result = use_case.execute(LoginCommand(email="user@example.com", password="secret"))

        self.assertEqual(
            result,
            LoginResult(
                tokens=TokenPair(access_token="access", refresh_token="refresh"),
                user=AuthenticatedUser(
                    id="u-1",
                    email="user@example.com",
                    name="User",
                ),
            ),
        )
        tracker.reset_failures.assert_called_once_with("user@example.com")

    def test_wraps_unexpected_errors_in_login_service_error(self):
        lookup = MagicMock()
        lookup.get_by_email.side_effect = RuntimeError("db down")
        tracker = MagicMock()
        tracker.is_rate_limited.return_value = False
        token_generator = MagicMock()
        use_case = DefaultLoginUserUseCase(
            user_lookup_port=lookup,
            attempt_tracker_port=tracker,
            token_generator_port=token_generator,
        )

        with self.assertRaises(LoginServiceError):
            use_case.execute(LoginCommand(email="user@example.com", password="secret"))


class LoginViewDependencyInjectionTest(APISimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_view_delegates_to_injected_use_case(self):
        use_case = MagicMock()
        result = MagicMock()
        result.tokens.access_token = "access"
        result.tokens.refresh_token = "refresh"
        result.user.id = "u-1"
        result.user.email = "user@example.com"
        result.user.name = "User"
        use_case.execute.return_value = result

        class TestableLoginView(LoginView):
            def get_login_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/login/",
            {"email": " USER@Example.COM ", "password": "secret"},
            format="json",
        )

        response = TestableLoginView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case.execute.assert_called_once_with(
            LoginCommand(email="user@example.com", password="secret")
        )


class DjangoLoginFailureTrackerTest(APISimpleTestCase):
    @patch("authentication.login.adapters.cache")
    def test_record_failure_falls_back_to_set_when_incr_raises_value_error(self, mock_cache):
        tracker = DjangoLoginFailureTracker()
        mock_cache.add.return_value = True
        mock_cache.incr.side_effect = ValueError

        result = tracker.record_failure("user@example.com")

        cache_key = tracker.get_cache_key("user@example.com")
        mock_cache.set.assert_called_once_with(cache_key, 1, tracker.TIME_WINDOW)
        self.assertEqual(result, 1)
