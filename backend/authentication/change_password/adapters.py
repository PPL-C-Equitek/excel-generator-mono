from __future__ import annotations

from authentication.change_password.contracts import (
    ChangePasswordAccountPort,
    ChangePasswordUseCase,
    PasswordChangedNotificationPort,
)
from authentication.change_password.use_cases import DefaultChangePasswordUseCase
from authentication.logout.adapters import DjangoTokenBlacklistRepository
from authentication.models import User
from authentication.services import send_password_changed_email


class DjangoChangePasswordAccountGateway(ChangePasswordAccountPort):
    def has_usable_password(self, user: User) -> bool:
        return user.has_usable_password()

    def check_password(self, user: User, password: str) -> bool:
        return user.check_password(password)

    def set_password(self, user: User, new_password: str) -> None:
        user.set_password(new_password)
        user.save(update_fields=["password"])


class DjangoPasswordChangedNotificationService(PasswordChangedNotificationPort):
    def send_password_changed_email(self, email: str) -> None:
        send_password_changed_email(email)


def build_change_password_use_case() -> ChangePasswordUseCase:
    return DefaultChangePasswordUseCase(
        account_port=DjangoChangePasswordAccountGateway(),
        notification_port=DjangoPasswordChangedNotificationService(),
        token_blacklist_port=DjangoTokenBlacklistRepository(),
    )
