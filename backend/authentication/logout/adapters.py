from __future__ import annotations

import hashlib
import jwt
from jwt import PyJWTError

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from authentication.logout.contracts import LogoutUserUseCase, TokenBlacklistPort
from authentication.logout.use_cases import DefaultLogoutUserUseCase


def _resolve_blacklist_timeout(payload: dict) -> int:
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return 7 * 24 * 60 * 60

    now_ts = int(timezone.now().timestamp())
    return max(exp - now_ts, 1)


class DjangoTokenBlacklistRepository(TokenBlacklistPort):
    def blacklist(self, refresh_token: str) -> None:
        if not refresh_token:
            raise ValueError("Refresh token is required")

        secret_key = getattr(settings, "JWT_SECRET_KEY", "")
        try:
            payload = jwt.decode(refresh_token, secret_key, algorithms=["HS256"])
        except PyJWTError as exc:
            raise ValueError("Invalid refresh token") from exc

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        cache_key = f"blacklisted_refresh_token:{token_hash}"
        timeout = _resolve_blacklist_timeout(payload)
        was_added = cache.add(cache_key, True, timeout=timeout)
        if not was_added:
            raise ValueError("Token already blacklisted")

    def is_blacklisted(self, refresh_token: str) -> bool:
        if not refresh_token:
            return False

        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        cache_key = f"blacklisted_refresh_token:{token_hash}"
        return bool(cache.get(cache_key, False))


class CallableTokenBlacklistRepository(TokenBlacklistPort):
    def __init__(self, blacklister) -> None:
        self._blacklister = blacklister

    def blacklist(self, refresh_token: str) -> None:
        self._blacklister(refresh_token)

    def is_blacklisted(self, refresh_token: str) -> bool:
        return False


def build_logout_user_use_case(
    token_blacklist_port: TokenBlacklistPort | None = None,
) -> LogoutUserUseCase:
    return DefaultLogoutUserUseCase(
        token_blacklist_port=token_blacklist_port or DjangoTokenBlacklistRepository()
    )
