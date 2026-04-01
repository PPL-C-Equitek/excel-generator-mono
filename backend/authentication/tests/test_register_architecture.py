from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APISimpleTestCase, APIRequestFactory

from authentication.register.adapters import DefaultRegistrationStrategyFactory
from authentication.register.entities import RegisterCommand, RegistrationResult, RegistrationUser
from authentication.register.exceptions import RegistrationServiceError
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
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            strategy_factory=strategy_factory,
        )

        result = use_case.execute(RegisterCommand(name="John", email="john@example.com"))

        self.assertEqual(result, RegistrationResult(message=REGISTER_SUCCESS_MESSAGE))
        lookup.find_by_email.assert_called_once_with("john@example.com")
        strategy_factory.create.assert_called_once_with(None)
        self.assertTrue(strategy.executed)
        self.assertEqual(strategy.received_command, RegisterCommand(name="John", email="john@example.com"))
        self.assertIsNone(strategy.received_user)

    def test_passes_existing_user_to_selected_strategy(self) -> None:
        existing_user = RegistrationUser(email="john@example.com", status="unverified")
        lookup = MagicMock()
        lookup.find_by_email.return_value = existing_user
        strategy = SpyRegistrationStrategy()
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            strategy_factory=strategy_factory,
        )

        result = use_case.execute(RegisterCommand(name="John", email="john@example.com"))

        self.assertEqual(result.message, REGISTER_SUCCESS_MESSAGE)
        strategy_factory.create.assert_called_once_with(existing_user)
        self.assertEqual(strategy.received_user, existing_user)

    def test_returns_generic_success_when_duplicate_race_raises_integrity_error(self) -> None:
        lookup = MagicMock()
        lookup.find_by_email.return_value = None
        strategy = MagicMock()
        strategy.execute.side_effect = IntegrityError("duplicate")
        strategy_factory = MagicMock()
        strategy_factory.create.return_value = strategy
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
            strategy_factory=strategy_factory,
        )

        result = use_case.execute(RegisterCommand(name="John", email="john@example.com"))

        self.assertEqual(result.message, REGISTER_SUCCESS_MESSAGE)

    def test_wraps_unexpected_errors_in_application_specific_exception(self) -> None:
        lookup = MagicMock()
        lookup.find_by_email.side_effect = RuntimeError("db down")
        strategy_factory = MagicMock()
        use_case = DefaultRegisterUserUseCase(
            lookup_port=lookup,
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case.execute.assert_called_once_with(
            RegisterCommand(name="John", email="john@example.com")
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
