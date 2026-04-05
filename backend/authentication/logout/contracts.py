from __future__ import annotations

from abc import ABC, abstractmethod

from authentication.logout.entities import LogoutCommand


class TokenBlacklistPort(ABC):
    @abstractmethod
    def blacklist(self, refresh_token: str) -> None:
        pass  # pragma: no cover


class LogoutUserUseCase(ABC):
    @abstractmethod
    def execute(self, command: LogoutCommand) -> None:
        pass  # pragma: no cover
