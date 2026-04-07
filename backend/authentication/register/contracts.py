from __future__ import annotations

from abc import ABC, abstractmethod

from authentication.register.entities import RegisterCommand, RegistrationResult, RegistrationUser


class RegistrationLookupPort(ABC):
    @abstractmethod
    def find_by_email(self, email: str) -> RegistrationUser | None:
        pass  # pragma: no cover


class RegistrationWriterPort(ABC):
    @abstractmethod
    def create_unverified_user(self, name: str, email: str) -> RegistrationUser:
        pass  # pragma: no cover


class VerificationNotificationPort(ABC):
    @abstractmethod
    def send_verification_email(self, email: str) -> None:
        pass  # pragma: no cover


class RegistrationStrategy(ABC):
    @abstractmethod
    def execute(
        self,
        command: RegisterCommand,
        existing_user: RegistrationUser | None = None,
    ) -> None:
        pass  # pragma: no cover


class RegistrationStrategyFactoryPort(ABC):
    @abstractmethod
    def create(self, existing_user: RegistrationUser | None) -> RegistrationStrategy:
        pass  # pragma: no cover


class RegisterUserUseCase(ABC):
    @abstractmethod
    def execute(self, command: RegisterCommand) -> RegistrationResult:
        pass  # pragma: no cover
