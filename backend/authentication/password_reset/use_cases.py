from __future__ import annotations

from django.core.signing import BadSignature, SignatureExpired

from authentication.password_reset.constants import (
    PASSWORD_RESET_COMPLETED_MESSAGE,
    PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE,
    PASSWORD_RESET_TOKEN_MAX_AGE,
)
from authentication.password_reset.contracts import (
    CompletePasswordResetUseCase,
    PasswordResetAccountPort,
    PasswordResetLookupPort,
    PasswordResetNotificationPort,
    PasswordResetTokenDecoderPort,
    RequestPasswordResetUseCase,
)
from authentication.password_reset.entities import (
    CompletePasswordResetCommand,
    PasswordResetEmailCommand,
    PasswordResetResult,
)
from authentication.password_reset.exceptions import (
    InvalidPasswordResetTokenError,
    PasswordResetServiceError,
    PasswordResetTokenExpiredError,
    PasswordResetUserNotFoundError,
)


class DefaultRequestPasswordResetUseCase(RequestPasswordResetUseCase):
    def __init__(
        self,
        lookup_port: PasswordResetLookupPort,
        notification_port: PasswordResetNotificationPort,
        success_message: str = PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE,
    ) -> None:
        self._lookup_port = lookup_port
        self._notification_port = notification_port
        self._success_message = success_message

    def execute(self, command: PasswordResetEmailCommand) -> PasswordResetResult:
        try:
            if self._lookup_port.has_verified_user(command.email):
                self._notification_port.send_password_reset_email(command.email)
            return PasswordResetResult(message=self._success_message)
        except Exception as exc:
            raise PasswordResetServiceError("Password reset request failed") from exc


class DefaultCompletePasswordResetUseCase(CompletePasswordResetUseCase):
    def __init__(
        self,
        token_decoder_port: PasswordResetTokenDecoderPort,
        account_port: PasswordResetAccountPort,
        success_message: str = PASSWORD_RESET_COMPLETED_MESSAGE,
    ) -> None:
        self._token_decoder_port = token_decoder_port
        self._account_port = account_port
        self._success_message = success_message

    def execute(self, command: CompletePasswordResetCommand) -> PasswordResetResult:
        try:
            email = self._token_decoder_port.decode(
                command.token,
                max_age=PASSWORD_RESET_TOKEN_MAX_AGE,
            )
        except SignatureExpired as exc:
            raise PasswordResetTokenExpiredError() from exc
        except (BadSignature, ValueError) as exc:
            raise InvalidPasswordResetTokenError() from exc
        except Exception as exc:
            raise PasswordResetServiceError("Password reset failed") from exc

        try:
            was_reset = self._account_port.reset_password_for_verified_user(
                email,
                command.password,
            )
        except Exception as exc:
            raise PasswordResetServiceError("Password reset failed") from exc

        if not was_reset:
            raise PasswordResetUserNotFoundError()

        return PasswordResetResult(message=self._success_message)
