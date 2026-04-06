from __future__ import annotations

from authentication.logout.contracts import LogoutUserUseCase, TokenBlacklistPort
from authentication.logout.entities import LogoutCommand


class DefaultLogoutUserUseCase(LogoutUserUseCase):
    def __init__(self, token_blacklist_port: TokenBlacklistPort) -> None:
        self._token_blacklist_port = token_blacklist_port

    def execute(self, command: LogoutCommand) -> None:
        self._token_blacklist_port.blacklist(command.refresh_token)
