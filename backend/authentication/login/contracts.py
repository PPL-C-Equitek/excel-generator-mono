from __future__ import annotations

from abc import ABC, abstractmethod

from authentication.login.entities import LoginCommand, LoginResult
from authentication.models import User


class LoginUserLookupPort(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> User:
        raise NotImplementedError


class LoginAttemptTrackerPort(ABC):
    @abstractmethod
    def is_rate_limited(self, email: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def record_failure(self, email: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def reset_failures(self, email: str) -> None:
        raise NotImplementedError


class LoginTokenGeneratorPort(ABC):
    @abstractmethod
    def generate(self, user_id: object, email: str) -> dict[str, str]:
        raise NotImplementedError


class LoginUserUseCase(ABC):
    @abstractmethod
    def execute(self, command: LoginCommand) -> LoginResult:
        raise NotImplementedError
