from __future__ import annotations

import uuid

from django.db import IntegrityError

from authentication.models import User
from authentication.register.contracts import RegisterUserUseCase, RegistrationLookupPort, RegistrationStrategyFactoryPort
from authentication.register.constants import REGISTER_SUCCESS_MESSAGE
from authentication.register.entities import RegisterCommand, RegistrationResult
from authentication.register.exceptions import (
    RegistrationConflictError,
    RegistrationServiceError,
    UnverifiedRegistrationError,
)


class DefaultRegisterUserUseCase(RegisterUserUseCase):
    def __init__(
        self,
        lookup_port: RegistrationLookupPort,
        strategy_factory: RegistrationStrategyFactoryPort,
        success_message: str = REGISTER_SUCCESS_MESSAGE,
    ) -> None:
        self._lookup_port = lookup_port
        self._strategy_factory = strategy_factory
        self._success_message = success_message

    def execute(self, command: RegisterCommand, password: str | None = None) -> RegistrationResult:
        try:
            existing_user = self._lookup_port.find_by_email(command.email)
            if existing_user is not None:
                if existing_user.status != "verified" and password:
                    user = User.objects.filter(email=command.email).first()
                    if user is not None:
                        user.set_password(password)
                        user.email_verification_nonce = uuid.uuid4()
                        user.save(update_fields=["password", "email_verification_nonce"])

                    unverified_strategy = self._strategy_factory.create(existing_user)
                    unverified_strategy.execute(command, existing_user)
                    raise UnverifiedRegistrationError(
                        "Email registered but unverified. A new link has been sent."
                    )
                raise RegistrationConflictError("Email is already registered.")
            strategy = self._strategy_factory.create(existing_user)
            strategy.execute(command, existing_user)
            return RegistrationResult(message=self._success_message)
        except UnverifiedRegistrationError:
            raise
        except RegistrationConflictError:
            raise
        except IntegrityError as exc:
            raise RegistrationConflictError("Email is already registered.") from exc
        except Exception as exc:
            raise RegistrationServiceError("Registration failed") from exc
