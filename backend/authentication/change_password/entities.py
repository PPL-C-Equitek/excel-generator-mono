from __future__ import annotations

from dataclasses import dataclass

from authentication.models import User


@dataclass(frozen=True)
class ChangePasswordCommand:
    user: User
    current_password: str
    new_password: str
    refresh_token: str | None = None


@dataclass(frozen=True)
class ChangePasswordResult:
    message: str
