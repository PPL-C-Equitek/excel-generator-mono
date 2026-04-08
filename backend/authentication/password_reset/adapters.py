from __future__ import annotations

from django.db.models import QuerySet

from authentication.models import User
from authentication.password_reset.constants import (
    PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE,
    PASSWORD_RESET_RESEND_REQUEST_SUCCESS_MESSAGE,
)
from authentication.password_reset.contracts import (
    CompletePasswordResetUseCase,
    PasswordResetAccountPort,
    PasswordResetLookupPort,
    PasswordResetNotificationPort,
    PasswordResetTokenDecoderPort,
    RequestPasswordResetUseCase,
)
from authentication.password_reset.use_cases import (
    DefaultCompletePasswordResetUseCase,
    DefaultRequestPasswordResetUseCase,
)
from authentication.services import decode_password_reset_token, send_password_reset_email


class DjangoPasswordResetUserRepository(
    PasswordResetLookupPort,
    PasswordResetAccountPort,
):
    def _verified_user_queryset(self, email: str) -> QuerySet[User]:
        return User.objects.filter(email=email, status="verified")

    def has_verified_user(self, email: str) -> bool:
        return self._verified_user_queryset(email).exists()

    def reset_password_for_verified_user(self, email: str, password: str) -> bool:
        user = self._verified_user_queryset(email).first()
        if user is None:
            return False

        user.set_password(password)
        user.save(update_fields=["password"])
        return True


class DjangoPasswordResetNotificationService(PasswordResetNotificationPort):
    def send_password_reset_email(self, email: str) -> None:
        send_password_reset_email(email)


class TimestampPasswordResetTokenDecoder(PasswordResetTokenDecoderPort):
    def decode(self, token, max_age):
        return decode_password_reset_token(token, max_age=max_age)


def build_request_password_reset_use_case() -> RequestPasswordResetUseCase:
    return DefaultRequestPasswordResetUseCase(
        lookup_port=DjangoPasswordResetUserRepository(),
        notification_port=DjangoPasswordResetNotificationService(),
        success_message=PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE,
    )


def build_resend_password_reset_use_case() -> RequestPasswordResetUseCase:
    return DefaultRequestPasswordResetUseCase(
        lookup_port=DjangoPasswordResetUserRepository(),
        notification_port=DjangoPasswordResetNotificationService(),
        success_message=PASSWORD_RESET_RESEND_REQUEST_SUCCESS_MESSAGE,
    )


def build_complete_password_reset_use_case() -> CompletePasswordResetUseCase:
    repository = DjangoPasswordResetUserRepository()
    return DefaultCompletePasswordResetUseCase(
        token_decoder_port=TimestampPasswordResetTokenDecoder(),
        account_port=repository,
    )
