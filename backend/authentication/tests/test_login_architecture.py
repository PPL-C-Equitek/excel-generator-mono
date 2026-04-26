from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APISimpleTestCase, APIRequestFactory

from authentication.login.adapters import (
    DjangoLoginFailureTracker,
    DjangoLoginTokenGenerator,
    DjangoLoginUserLookupGateway,
    build_login_use_case,
)
from authentication.login.contracts import (
    LoginAttemptTrackerPort,
    LoginTokenGeneratorPort,
    LoginUserLookupPort,
    LoginUserUseCase,
)
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
        # Positive
    def test_returns_login_result_and_resets_failure_counter_on_success(self):
        user = MagicMock()
        user.id = "u-1"
        user.email = "user@example.com"
        user.name = "User"
        user.status = "verified"
        user.session_version = 3
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
        token_generator.generate.assert_called_once_with(
            "u-1",
            "user@example.com",
            session_version=3,
        )
        tracker.reset_failures.assert_called_once_with("user@example.com")

    # Negative
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

    def test_resolve_session_version_returns_default_for_non_int(self):
        user = MagicMock(session_version="v2")

        self.assertEqual(DefaultLoginUserUseCase._resolve_session_version(user), 1)

    # Edge Case
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
    # Positive
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
    # Positive
    @patch("authentication.login.adapters.cache")
    def test_reset_failures_deletes_cache_key(self, mock_cache):
        tracker = DjangoLoginFailureTracker()
        cache_key = tracker.get_cache_key("user@example.com")

        tracker.reset_failures("user@example.com")

        mock_cache.delete.assert_called_once_with(cache_key)

    # Edge Case
    @patch("authentication.login.adapters.cache")
    def test_record_failure_falls_back_to_set_when_incr_raises_value_error(self, mock_cache):
        tracker = DjangoLoginFailureTracker()
        mock_cache.add.return_value = True
        mock_cache.incr.side_effect = ValueError

        result = tracker.record_failure("user@example.com")

        cache_key = tracker.get_cache_key("user@example.com")
        mock_cache.set.assert_called_once_with(cache_key, 1, tracker.TIME_WINDOW)
        self.assertEqual(result, 1)

    @patch("authentication.login.adapters.cache")
    def test_is_rate_limited_returns_true_when_failure_limit_reached(self, mock_cache):
        tracker = DjangoLoginFailureTracker()
        cache_key = tracker.get_cache_key("user@example.com")
        mock_cache.get.return_value = tracker.FAILURE_LIMIT

        result = tracker.is_rate_limited("user@example.com")

        mock_cache.get.assert_called_once_with(cache_key, 0)
        self.assertTrue(result)

class LoginAdaptersTest(APISimpleTestCase):
    # Positive
    @patch("authentication.login.adapters.User")
    def test_user_lookup_gateway_delegates_to_user_manager(self, mock_user):
        gateway = DjangoLoginUserLookupGateway()
        expected_user = MagicMock()
        mock_user.objects.get.return_value = expected_user

        result = gateway.get_by_email("user@example.com")

        mock_user.objects.get.assert_called_once_with(email="user@example.com")
        self.assertIs(result, expected_user)

    @patch("authentication.login.adapters.generate_tokens")
    def test_token_generator_delegates_to_generate_tokens_function(self, mock_generate_tokens):
        token_generator = DjangoLoginTokenGenerator()
        mock_generate_tokens.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
        }

        result = token_generator.generate("user-id", "user@example.com", session_version=2)

        mock_generate_tokens.assert_called_once_with(
            "user-id",
            "user@example.com",
            session_version=2,
        )
        self.assertEqual(result["access_token"], "access")
        self.assertEqual(result["refresh_token"], "refresh")

    def test_build_login_use_case_returns_default_use_case_instance(self):
        use_case = build_login_use_case()

        self.assertIsInstance(use_case, DefaultLoginUserUseCase)


class LoginContractsTest(APISimpleTestCase):
    # Negative
    def test_user_lookup_port_base_method_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            LoginUserLookupPort.get_by_email(object(), "user@example.com")

    def test_attempt_tracker_port_base_methods_raise_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            LoginAttemptTrackerPort.is_rate_limited(object(), "user@example.com")
        with self.assertRaises(NotImplementedError):
            LoginAttemptTrackerPort.record_failure(object(), "user@example.com")
        with self.assertRaises(NotImplementedError):
            LoginAttemptTrackerPort.reset_failures(object(), "user@example.com")

    def test_token_generator_port_base_method_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            LoginTokenGeneratorPort.generate(object(), "user-id", "user@example.com", 1)

    def test_use_case_port_base_method_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            LoginUserUseCase.execute(
                object(),
                LoginCommand(email="user@example.com", password="secret"),
            )
