from __future__ import annotations

import logging

from authentication.change_password.constants import (
    CHANGE_PASSWORD_SUCCESS_MESSAGE,
)
from authentication.change_password.contracts import (
    ChangePasswordAccountPort,
    ChangePasswordUseCase,
    PasswordChangedNotificationPort,
)
from authentication.change_password.entities import (
    ChangePasswordCommand,
    ChangePasswordResult,
)
from authentication.change_password.exceptions import (
    ChangePasswordServiceError,
    CurrentPasswordRequiredError,
    InvalidCurrentPasswordError,
    PasswordReuseError,
)
from authentication.logout.contracts import TokenBlacklistPort

logger = logging.getLogger(__name__)


class DefaultChangePasswordUseCase(ChangePasswordUseCase):
    def __init__(
        self,
        account_port: ChangePasswordAccountPort,
        notification_port: PasswordChangedNotificationPort,
        token_blacklist_port: TokenBlacklistPort,
        success_message: str = CHANGE_PASSWORD_SUCCESS_MESSAGE,
    ) -> None:
        self._account_port = account_port
        self._notification_port = notification_port
        self._token_blacklist_port = token_blacklist_port
        self._success_message = success_message

    def execute(self, command: ChangePasswordCommand) -> ChangePasswordResult:
        try:
            if self._account_port.has_usable_password(command.user):
                if not command.current_password.strip():
                    raise CurrentPasswordRequiredError()
                if not self._account_port.check_password(
                    command.user,
                    command.current_password,
                ):
                    raise InvalidCurrentPasswordError()

            if self._account_port.check_password(command.user, command.new_password):
                raise PasswordReuseError()

            self._account_port.set_password(command.user, command.new_password)
            self._blacklist_refresh_token(command.refresh_token)
            self._send_notification(command.user.email)
            return ChangePasswordResult(message=self._success_message)
        except (
            CurrentPasswordRequiredError,
            InvalidCurrentPasswordError,
            PasswordReuseError,
        ):
            raise
        except Exception as exc:
            raise ChangePasswordServiceError("Password change failed") from exc

    def _blacklist_refresh_token(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        try:
            self._token_blacklist_port.blacklist(refresh_token)
        except Exception:
            logger.exception("Failed to blacklist refresh token after password change.")

    def _send_notification(self, email: str) -> None:
        try:
            self._notification_port.send_password_changed_email(email)
        except Exception:
            logger.exception(
                "Failed to send password changed notification to %s.",
                email,
            )
