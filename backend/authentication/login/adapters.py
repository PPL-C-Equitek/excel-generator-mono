from __future__ import annotations

from django.core.cache import cache

from authentication.login.contracts import (
    LoginAttemptTrackerPort,
    LoginTokenGeneratorPort,
    LoginUserLookupPort,
    LoginUserUseCase,
)
from authentication.login.use_cases import DefaultLoginUserUseCase
from authentication.models import User
from authentication.services import generate_tokens


class DjangoLoginUserLookupGateway(LoginUserLookupPort):
    def get_by_email(self, email: str) -> User:
        return User.objects.get(email=email)


class DjangoLoginFailureTracker(LoginAttemptTrackerPort):
    FAILURE_LIMIT = 5
    TIME_WINDOW = 15 * 60

    @staticmethod
    def get_cache_key(email: str) -> str:
        return f"login_failures:{email.lower().strip()}"

    @classmethod
    def get_cache_backend(cls):
        return cache

    def is_rate_limited(self, email: str) -> bool:
        cache_key = self.get_cache_key(email)
        cache_backend = self.get_cache_backend()
        failures = cache_backend.get(cache_key, 0)
        return failures >= self.FAILURE_LIMIT

    def record_failure(self, email: str) -> int:
        cache_key = self.get_cache_key(email)
        cache_backend = self.get_cache_backend()
        cache_backend.add(cache_key, 0, self.TIME_WINDOW)

        try:
            return cache_backend.incr(cache_key)
        except ValueError:
            cache_backend.set(cache_key, 1, self.TIME_WINDOW)
            return 1

    def reset_failures(self, email: str) -> None:
        cache_key = self.get_cache_key(email)
        cache_backend = self.get_cache_backend()
        cache_backend.delete(cache_key)


class DjangoLoginTokenGenerator(LoginTokenGeneratorPort):
    def generate(self, user_id: object, email: str) -> dict[str, str]:
        return generate_tokens(user_id, email)


def build_login_use_case() -> LoginUserUseCase:
    return DefaultLoginUserUseCase(
        user_lookup_port=DjangoLoginUserLookupGateway(),
        attempt_tracker_port=DjangoLoginFailureTracker(),
        token_generator_port=DjangoLoginTokenGenerator(),
    )
