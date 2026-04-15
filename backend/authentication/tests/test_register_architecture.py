from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APISimpleTestCase, APIRequestFactory

from authentication.register.adapters import (
    DefaultRegistrationStrategyFactory,
    DjangoRegistrationWriterRepository,
)
from authentication.register.entities import RegisterCommand, RegistrationResult, RegistrationUser
from authentication.register.exceptions import (
    RegistrationConflictError,
    RegistrationServiceError,
    UnverifiedRegistrationError,
)
from authentication.register.http import RegisterView
from authentication.register.strategies import (
    ExistingUnverifiedUserRegistrationStrategy,
    ExistingVerifiedUserRegistrationStrategy,
    NewUserRegistrationStrategy,
)
from authentication.register.use_cases import DefaultRegisterUserUseCase
from authentication.register.constants import REGISTER_SUCCESS_MESSAGE


@dataclass
class SpyRegistrationStrategy:
    executed: bool = False
    received_command: RegisterCommand | None = None
    received_user: RegistrationUser | None = None

    def execute(
        self,
        command: RegisterCommand,
        existing_user: RegistrationUser | None = None,
    ) -> None:
        self.executed = True
        self.received_command = command
        self.received_user = existing_user


class RegisterCommandTest(APISimpleTestCase):
    def test_normalizes_email_for_consistent_downstream_processing(self) -> None:
        command = RegisterCommand(name="John", email="  John@Example.COM  ")

        self.assertEqual(command.email, "john@example.com")


class DefaultRegisterUserUseCaseTest(APISimpleTestCase):
    def test_uses_factory_selected_strategy_for_new_user_flow(self) -> None:
        lookup = MagicMock()
        lookup.find_by_email.return_value = None
        strategy = SpyRegistrationStrategy()
        writer = MagicMock()
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            registration_writer=writer,
            strategy_factory=strategy_factory,
        )

        result = use_case.execute(RegisterCommand(name="John", email="john@example.com"))

        self.assertEqual(result, RegistrationResult(message=REGISTER_SUCCESS_MESSAGE))
        lookup.find_by_email.assert_called_once_with("john@example.com")
        strategy_factory.create.assert_called_once_with(None)
        self.assertTrue(strategy.executed)
        self.assertEqual(strategy.received_command, RegisterCommand(name="John", email="john@example.com"))
        self.assertIsNone(strategy.received_user)

    def test_raises_unverified_registration_error_and_executes_unverified_strategy_for_unverified_user(self) -> None:
        existing_user = RegistrationUser(email="john@example.com", status="unverified")
        lookup = MagicMock()
        lookup.find_by_email.return_value = existing_user
        strategy = MagicMock()
        writer = MagicMock()
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            registration_writer=writer,
            strategy_factory=strategy_factory,
        )

        with patch("authentication.register.use_cases.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__enter__.return_value = None
            mock_atomic.return_value.__exit__.return_value = None

            with self.assertRaises(UnverifiedRegistrationError):
                use_case.execute(RegisterCommand(name="John", email="john@example.com"))

        lookup.find_by_email.assert_called_once_with("john@example.com")
        strategy_factory.create.assert_called_once_with(existing_user)
        strategy.execute.assert_called_once_with(
            RegisterCommand(name="John", email="john@example.com"),
            existing_user,
        )
        writer.update_unverified_user_password.assert_not_called()

    def test_updates_password_before_resending_for_unverified_user_when_password_is_provided(self) -> None:
        existing_user = RegistrationUser(email="john@example.com", status="unverified")
        lookup = MagicMock()
        lookup.find_by_email.return_value = existing_user
        writer = MagicMock()
        strategy = MagicMock()
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            registration_writer=writer,
            strategy_factory=strategy_factory,
        )

        with patch("authentication.register.use_cases.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__enter__.return_value = None
            mock_atomic.return_value.__exit__.return_value = None

            with self.assertRaises(UnverifiedRegistrationError):
                use_case.execute(
                    RegisterCommand(name="John", email="john@example.com"),
                    password="Strong#123",
                )

        writer.update_unverified_user_password.assert_called_once_with(
            email="john@example.com",
            password="Strong#123",
        )
        strategy.execute.assert_called_once_with(
            RegisterCommand(name="John", email="john@example.com"),
            existing_user,
        )

    def test_raises_registration_conflict_error_when_duplicate_race_raises_integrity_error(self) -> None:
        lookup = MagicMock()
        lookup.find_by_email.return_value = None
        strategy = MagicMock()
        strategy.execute.side_effect = IntegrityError("duplicate")
        writer = MagicMock()
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            registration_writer=writer,
            strategy_factory=strategy_factory,
        )

        with self.assertRaises(RegistrationConflictError):
            use_case.execute(RegisterCommand(name="John", email="john@example.com"))

    def test_wraps_unexpected_errors_in_application_specific_exception(self) -> None:
        lookup = MagicMock()
        lookup.find_by_email.side_effect = RuntimeError("db down")
        writer = MagicMock()
        strategy_factory = MagicMock()
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            registration_writer=writer,
            strategy_factory=strategy_factory,
        )

        with self.assertRaises(RegistrationServiceError):
            use_case.execute(RegisterCommand(name="John", email="john@example.com"))


class DefaultRegistrationStrategyFactoryTest(APISimpleTestCase):
    def test_returns_new_user_strategy_when_lookup_finds_nothing(self) -> None:
        new_user_strategy = MagicMock()
        existing_unverified_strategy = MagicMock()
        existing_verified_strategy = MagicMock()
        factory = DefaultRegistrationStrategyFactory(
            new_user_strategy=new_user_strategy,
            existing_unverified_strategy=existing_unverified_strategy,
            existing_verified_strategy=existing_verified_strategy,
        )

        selected_strategy = factory.create(None)

        self.assertIs(selected_strategy, new_user_strategy)

    def test_returns_existing_unverified_strategy_for_unverified_user(self) -> None:
        new_user_strategy = MagicMock()
        existing_unverified_strategy = MagicMock()
        existing_verified_strategy = MagicMock()
        factory = DefaultRegistrationStrategyFactory(
            new_user_strategy=new_user_strategy,
            existing_unverified_strategy=existing_unverified_strategy,
            existing_verified_strategy=existing_verified_strategy,
        )

        selected_strategy = factory.create(
            RegistrationUser(email="john@example.com", status="unverified")
        )

        self.assertIs(selected_strategy, existing_unverified_strategy)

    def test_returns_existing_verified_strategy_for_verified_user(self) -> None:
        new_user_strategy = MagicMock()
        existing_unverified_strategy = MagicMock()
        existing_verified_strategy = MagicMock()
        factory = DefaultRegistrationStrategyFactory(
            new_user_strategy=new_user_strategy,
            existing_unverified_strategy=existing_unverified_strategy,
            existing_verified_strategy=existing_verified_strategy,
        )

        selected_strategy = factory.create(
            RegistrationUser(email="john@example.com", status="verified")
        )

        self.assertIs(selected_strategy, existing_verified_strategy)


class RegistrationStrategyTest(APISimpleTestCase):
    def test_existing_unverified_strategy_resends_verification_email(self) -> None:
        notifier = MagicMock()
        strategy = ExistingUnverifiedUserRegistrationStrategy(notifier=notifier)
        existing_user = RegistrationUser(email="john@example.com", status="unverified")

        strategy.execute(RegisterCommand(name="John", email="john@example.com"), existing_user)

        notifier.send_verification_email.assert_called_once_with("john@example.com")

    def test_existing_verified_strategy_does_not_trigger_side_effects(self) -> None:
        strategy = ExistingVerifiedUserRegistrationStrategy()

        strategy.execute(
            RegisterCommand(name="John", email="john@example.com"),
            RegistrationUser(email="john@example.com", status="verified"),
        )

    def test_existing_unverified_strategy_requires_existing_user_context(self) -> None:
        notifier = MagicMock()
        strategy = ExistingUnverifiedUserRegistrationStrategy(notifier=notifier)

        with self.assertRaises(ValueError):
            strategy.execute(RegisterCommand(name="John", email="john@example.com"))

    def test_new_user_strategy_creates_unverified_user_without_password_then_sends_email(self) -> None:
        creator = MagicMock()
        notifier = MagicMock()
        creator.create_unverified_user.return_value = RegistrationUser(
            email="john@example.com",
            status="unverified",
        )
        strategy = NewUserRegistrationStrategy(
            registration_writer=creator,
            notifier=notifier,
        )

        strategy.execute(RegisterCommand(name="John", email="john@example.com"))

        creator.create_unverified_user.assert_called_once_with(
            name="John",
            email="john@example.com",
        )
        notifier.send_verification_email.assert_called_once_with("john@example.com")


class RegisterViewDependencyInjectionTest(APISimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()

    def test_view_delegates_to_injected_use_case(self) -> None:
        use_case = MagicMock()
        use_case.execute.return_value = RegistrationResult(message=REGISTER_SUCCESS_MESSAGE)

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {"name": "John", "email": "  John@Example.COM  "},
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        use_case.execute.assert_called_once_with(
            RegisterCommand(name="John", email="john@example.com"),
            password=None,
        )

    def test_view_passes_valid_password_from_serializer(self) -> None:
        use_case = MagicMock()
        use_case.execute.return_value = RegistrationResult(message=REGISTER_SUCCESS_MESSAGE)

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {
                "name": "John",
                "email": "john@example.com",
                "password": "Strong#123",
            },
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        use_case.execute.assert_called_once_with(
            RegisterCommand(name="John", email="john@example.com"),
            password="Strong#123",
        )

    def test_view_returns_500_when_use_case_raises_application_error(self) -> None:
        use_case = MagicMock()
        use_case.execute.side_effect = RegistrationServiceError("unexpected")

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {"name": "John", "email": "john@example.com"},
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "An internal server error occurred")

    def test_view_returns_500_when_use_case_raises_unhandled_exception(self) -> None:
        use_case = MagicMock()
        use_case.execute.side_effect = Exception("unexpected boom")

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {"name": "John", "email": "john@example.com"},
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "An internal server error occurred")

    def test_view_short_circuits_before_use_case_when_payload_is_invalid(self) -> None:
        use_case = MagicMock()

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {"name": "John", "email": "not-an-email"},
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        use_case.execute.assert_not_called()

    def test_view_short_circuits_when_password_type_is_invalid(self) -> None:
        use_case = MagicMock()

        class TestableRegisterView(RegisterView):
            def get_register_use_case(self):  # type: ignore[override]
                return use_case

        request = self.factory.post(
            "/auth/register/",
            {"name": "John", "email": "john@example.com", "password": {"bad": "type"}},
            format="json",
        )

        response = TestableRegisterView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["errors"]["password"][0], "Not a valid string.")
        use_case.execute.assert_not_called()


class DjangoRegistrationWriterRepositoryTest(APISimpleTestCase):
    @patch("authentication.register.adapters.User")
    def test_update_unverified_user_password_is_noop_when_user_missing(self, mock_user_model):
        mock_user_model.objects.filter.return_value.first.return_value = None

        repository = DjangoRegistrationWriterRepository()
        repository.update_unverified_user_password(
            email="missing@example.com",
            password="Strong#123",
        )

        mock_user_model.objects.filter.assert_called_once_with(
            email="missing@example.com",
            status="unverified",
        )

    @patch("authentication.register.adapters.User")
    def test_update_unverified_user_password_only_targets_unverified_users(self, mock_user_model):
        mock_user = MagicMock()
        mock_user_model.objects.filter.return_value.first.return_value = mock_user

        repository = DjangoRegistrationWriterRepository()
        repository.update_unverified_user_password(
            email="pending@example.com",
            password="Strong#123",
        )

        mock_user_model.objects.filter.assert_called_once_with(
            email="pending@example.com",
            status="unverified",
        )
        mock_user.set_password.assert_called_once_with("Strong#123")
        mock_user.save.assert_called_once_with(update_fields=["password"])
