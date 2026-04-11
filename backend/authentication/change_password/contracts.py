from __future__ import annotations

from abc import ABC, abstractmethod

from authentication.change_password.entities import (
    ChangePasswordCommand,
    ChangePasswordResult,
)
from authentication.models import User


class ChangePasswordAccountPort(ABC):
    @abstractmethod
    def has_usable_password(self, user: User) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def check_password(self, user: User, password: str) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def set_password(self, user: User, new_password: str) -> None:
        pass  # pragma: no cover


class PasswordChangedNotificationPort(ABC):
    @abstractmethod
    def send_password_changed_email(self, email: str) -> None:
        pass  # pragma: no cover


class ChangePasswordUseCase(ABC):
    @abstractmethod
    def execute(self, command: ChangePasswordCommand) -> ChangePasswordResult:
        pass  # pragma: no cover
