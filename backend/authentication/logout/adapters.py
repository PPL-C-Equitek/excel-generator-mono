from __future__ import annotations

import jwt
from jwt import PyJWTError

from django.conf import settings
from django.core.cache import cache

from authentication.logout.contracts import LogoutUserUseCase, TokenBlacklistPort
from authentication.logout.use_cases import DefaultLogoutUserUseCase


class DjangoTokenBlacklistRepository(TokenBlacklistPort):
    def blacklist(self, refresh_token: str) -> None:
        if not refresh_token:  # pragma: no cover
            raise ValueError("Refresh token is required")

        secret_key = getattr(settings, "JWT_SECRET_KEY", "")
        try:
            payload = jwt.decode(refresh_token, secret_key, algorithms=["HS256"])
        except PyJWTError as exc:  # pragma: no cover
            raise ValueError("Invalid refresh token") from exc

        if payload.get("type") != "refresh":  # pragma: no cover
            raise ValueError("Invalid token type")

        cache_key = f"blacklisted_refresh_token:{refresh_token}"
        if cache.get(cache_key):  # pragma: no cover
            raise ValueError("Token already blacklisted")

        cache.set(cache_key, True, timeout=7 * 24 * 60 * 60)


class CallableTokenBlacklistRepository(TokenBlacklistPort):
    def __init__(self, blacklister) -> None:
        self._blacklister = blacklister

    def blacklist(self, refresh_token: str) -> None:
        self._blacklister(refresh_token)
        DjangoTokenBlacklistRepository().blacklist(refresh_token)


def build_logout_user_use_case(
    token_blacklist_port: TokenBlacklistPort | None = None,
) -> LogoutUserUseCase:
    return DefaultLogoutUserUseCase(
        token_blacklist_port=token_blacklist_port or DjangoTokenBlacklistRepository()
    )
