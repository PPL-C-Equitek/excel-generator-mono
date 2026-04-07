from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta

from authentication.password_reset.entities import (
    CompletePasswordResetCommand,
    PasswordResetEmailCommand,
    PasswordResetResult,
)


class PasswordResetLookupPort(ABC):
    @abstractmethod
    def has_verified_user(self, email: str) -> bool:
        pass  # pragma: no cover


class PasswordResetAccountPort(ABC):
    @abstractmethod
    def reset_password_for_verified_user(self, email: str, password: str) -> bool:
        pass  # pragma: no cover


class PasswordResetNotificationPort(ABC):
    @abstractmethod
    def send_password_reset_email(self, email: str) -> None:
        pass  # pragma: no cover


class PasswordResetTokenDecoderPort(ABC):
    @abstractmethod
    def decode(self, token: str, max_age: timedelta) -> str:
        pass  # pragma: no cover


class RequestPasswordResetUseCase(ABC):
    @abstractmethod
    def execute(self, command: PasswordResetEmailCommand) -> PasswordResetResult:
        pass  # pragma: no cover


class CompletePasswordResetUseCase(ABC):
    @abstractmethod
    def execute(self, command: CompletePasswordResetCommand) -> PasswordResetResult:
        pass  # pragma: no cover
