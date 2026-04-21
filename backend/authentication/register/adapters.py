from __future__ import annotations

from django.db.models import Model

from authentication.models import User
from authentication.register.contracts import (
    RegisterUserUseCase,
    RegistrationLookupPort,
    RegistrationStrategy,
    RegistrationStrategyFactoryPort,
    RegistrationWriterPort,
    VerificationNotificationPort,
)
from authentication.register.entities import RegistrationUser
from authentication.register.strategies import (
    ExistingUnverifiedUserRegistrationStrategy,
    ExistingVerifiedUserRegistrationStrategy,
    NewUserRegistrationStrategy,
)
from authentication.register.use_cases import DefaultRegisterUserUseCase
from authentication.services import send_verification_email


class DjangoRegistrationLookupRepository(RegistrationLookupPort):
    def find_by_email(self, email: str) -> RegistrationUser | None:
        user = User.objects.filter(email=email).first()
        if user is None:
            return None
        return _map_user(user)


class DjangoRegistrationWriterRepository(RegistrationWriterPort):
    def create_unverified_user(self, name: str, email: str) -> RegistrationUser:
        user = User.objects.create_user(
            name=name,
            email=email,
            status="unverified",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return _map_user(user)

    def update_unverified_user_password(self, email: str, password: str) -> None:
        user = (
            User.objects.filter(email=email, status="unverified")
            .select_for_update()
            .first()
        )
        if user is None:
            return

        user.set_password(password)
        user.save(update_fields=["password"])


class DjangoVerificationNotificationService(VerificationNotificationPort):
    def send_verification_email(self, email: str) -> None:
        send_verification_email(email)


class DefaultRegistrationStrategyFactory(RegistrationStrategyFactoryPort):
    def __init__(
        self,
        new_user_strategy: RegistrationStrategy,
        existing_unverified_strategy: RegistrationStrategy,
        existing_verified_strategy: RegistrationStrategy,
    ) -> None:
        self._new_user_strategy = new_user_strategy
        self._existing_unverified_strategy = existing_unverified_strategy
        self._existing_verified_strategy = existing_verified_strategy

    def create(self, existing_user: RegistrationUser | None) -> RegistrationStrategy:
        if existing_user is None:
            return self._new_user_strategy
        if existing_user.status == "verified":
            return self._existing_verified_strategy
        return self._existing_unverified_strategy


def build_register_user_use_case() -> RegisterUserUseCase:
    notifier = DjangoVerificationNotificationService()
    writer = DjangoRegistrationWriterRepository()
    strategy_factory = DefaultRegistrationStrategyFactory(
        new_user_strategy=NewUserRegistrationStrategy(
            registration_writer=writer,
            notifier=notifier,
        ),
        existing_unverified_strategy=ExistingUnverifiedUserRegistrationStrategy(
            notifier=notifier,
        ),
        existing_verified_strategy=ExistingVerifiedUserRegistrationStrategy(),
    )
    return DefaultRegisterUserUseCase(
        lookup_port=DjangoRegistrationLookupRepository(),
        registration_writer=writer,
        strategy_factory=strategy_factory,
    )


def _map_user(user: Model) -> RegistrationUser:
    return RegistrationUser(email=str(user.email), status=str(user.status))
