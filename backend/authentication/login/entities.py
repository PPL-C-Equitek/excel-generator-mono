from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", self.email.lower().strip())


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: str
    email: str
    name: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    tokens: TokenPair
    user: AuthenticatedUser
