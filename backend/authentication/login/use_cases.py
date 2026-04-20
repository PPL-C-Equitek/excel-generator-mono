from __future__ import annotations

import logging

from authentication.login.contracts import (
    LoginAttemptTrackerPort,
    LoginTokenGeneratorPort,
    LoginUserLookupPort,
    LoginUserUseCase,
)
from authentication.login.entities import (
    AuthenticatedUser,
    LoginCommand,
    LoginResult,
    TokenPair,
)
from authentication.login.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    LoginRateLimitedError,
    LoginServiceError,
)
from authentication.models import User

logger = logging.getLogger(__name__)

LOGIN_USE_CASE_OPERATION_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
)


class DefaultLoginUserUseCase(LoginUserUseCase):
    def __init__(
        self,
        user_lookup_port: LoginUserLookupPort,
        attempt_tracker_port: LoginAttemptTrackerPort,
        token_generator_port: LoginTokenGeneratorPort,
    ) -> None:
        self._user_lookup_port = user_lookup_port
        self._attempt_tracker_port = attempt_tracker_port
        self._token_generator_port = token_generator_port

    def execute(self, command: LoginCommand) -> LoginResult:
        try:
            if self._attempt_tracker_port.is_rate_limited(command.email):
                raise LoginRateLimitedError()

            user = self._lookup_user(command.email)

            if user.status != "verified":
                logger.warning("Login failed for %s: email not verified.", command.email)
                self._attempt_tracker_port.record_failure(command.email)
                raise EmailNotVerifiedError()

            if not user.check_password(command.password):
                logger.warning("Login failed for %s: incorrect password.", command.email)
                self._attempt_tracker_port.record_failure(command.email)
                raise InvalidCredentialsError()

            token_data = self._token_generator_port.generate(user.id, user.email)
            self._attempt_tracker_port.reset_failures(command.email)

            return LoginResult(
                tokens=TokenPair(
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                ),
                user=AuthenticatedUser(
                    id=str(user.id),
                    email=user.email,
                    name=user.name,
                ),
            )
        except (LoginRateLimitedError, InvalidCredentialsError, EmailNotVerifiedError):
            raise
        except LOGIN_USE_CASE_OPERATION_ERRORS as exc:
            raise LoginServiceError("Login failed") from exc

    def _lookup_user(self, email: str) -> User:
        try:
            return self._user_lookup_port.get_by_email(email)
        except User.DoesNotExist as exc:
            logger.warning("Login failed for %s: user not found.", email)
            self._attempt_tracker_port.record_failure(email)
            raise InvalidCredentialsError() from exc
