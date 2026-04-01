from __future__ import annotations

from authentication.register.contracts import RegistrationStrategy, RegistrationWriterPort, VerificationNotificationPort
from authentication.register.entities import RegisterCommand, RegistrationUser


class ExistingVerifiedUserRegistrationStrategy(RegistrationStrategy):
    def execute(
        self,
        command: RegisterCommand,
        existing_user: RegistrationUser | None = None,
    ) -> None:
        return None


class ExistingUnverifiedUserRegistrationStrategy(RegistrationStrategy):
    def __init__(self, notifier: VerificationNotificationPort) -> None:
        self._notifier = notifier

    def execute(
        self,
        command: RegisterCommand,
        existing_user: RegistrationUser | None = None,
    ) -> None:
        if existing_user is None:
            raise ValueError("existing_user is required for unverified-user strategy")
        self._notifier.send_verification_email(existing_user.email)


class NewUserRegistrationStrategy(RegistrationStrategy):
    def __init__(
        self,
        registration_writer: RegistrationWriterPort,
        notifier: VerificationNotificationPort,
    ) -> None:
        self._registration_writer = registration_writer
        self._notifier = notifier

    def execute(
        self,
        command: RegisterCommand,
        existing_user: RegistrationUser | None = None,
    ) -> None:
        user = self._registration_writer.create_unverified_user(
            name=command.name,
            email=command.email,
        )
        self._notifier.send_verification_email(user.email)
