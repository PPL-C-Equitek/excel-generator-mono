from __future__ import annotations

from django.db import transaction
from django.db import IntegrityError

from authentication.register.contracts import (
    RegisterUserUseCase,
    RegistrationLookupPort,
    RegistrationStrategyFactoryPort,
    RegistrationWriterPort,
)
from authentication.register.constants import REGISTER_SUCCESS_MESSAGE
from authentication.register.entities import RegisterCommand, RegistrationResult, RegistrationUser
from authentication.register.exceptions import (
    RegistrationConflictError,
    RegistrationServiceError,
    UnverifiedRegistrationError,
)


class DefaultRegisterUserUseCase(RegisterUserUseCase):
    def __init__(
        self,
        lookup_port: RegistrationLookupPort,
        registration_writer: RegistrationWriterPort,
        strategy_factory: RegistrationStrategyFactoryPort,
        success_message: str = REGISTER_SUCCESS_MESSAGE,
    ) -> None:
        self._lookup_port = lookup_port
        self._registration_writer = registration_writer
        self._strategy_factory = strategy_factory
        self._success_message = success_message

    def execute(self, command: RegisterCommand, password: str | None = None) -> RegistrationResult:
        try:
            existing_user = self._lookup_port.find_by_email(command.email)
            if existing_user is None:
                self._register_new_user(command)
                return RegistrationResult(message=self._success_message)

            if existing_user.status != "verified":
                self._reregister_unverified_user(command=command, password=password, existing_user=existing_user)

            raise RegistrationConflictError("Email is already registered.")

        except UnverifiedRegistrationError:
            raise
        except RegistrationConflictError:
            raise
        except IntegrityError as exc:
            raise RegistrationConflictError("Email is already registered.") from exc
        except Exception as exc:
            raise RegistrationServiceError("Registration failed") from exc

    def _register_new_user(self, command: RegisterCommand) -> None:
        strategy = self._strategy_factory.create(None)
        strategy.execute(command, None)

    def _reregister_unverified_user(
        self,
        command: RegisterCommand,
        password: str | None,
        existing_user: RegistrationUser,
    ) -> None:
        with transaction.atomic():
            if password:
                self._registration_writer.update_unverified_user_password(
                    email=command.email,
                    password=password,
                )

            unverified_strategy = self._strategy_factory.create(existing_user)
            unverified_strategy.execute(command, existing_user)

        raise UnverifiedRegistrationError(
            "Email registered but unverified. A new link has been sent."
        )
