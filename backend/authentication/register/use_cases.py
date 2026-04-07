from __future__ import annotations

from django.db import IntegrityError

from authentication.register.contracts import RegisterUserUseCase, RegistrationLookupPort, RegistrationStrategyFactoryPort
from authentication.register.constants import REGISTER_SUCCESS_MESSAGE
from authentication.register.entities import RegisterCommand, RegistrationResult
from authentication.register.exceptions import RegistrationServiceError


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

    def execute(self, command: RegisterCommand) -> RegistrationResult:
        try:
            existing_user = self._lookup_port.find_by_email(command.email)
            strategy = self._strategy_factory.create(existing_user)
            strategy.execute(command, existing_user)
            return RegistrationResult(message=self._success_message)
        except IntegrityError:
            return RegistrationResult(message=self._success_message)
        except Exception as exc:
            raise RegistrationServiceError("Registration failed") from exc
