from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordResetEmailCommand:
    email: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", self.email.lower().strip())


@dataclass(frozen=True)
class CompletePasswordResetCommand:
    token: str
    password: str


@dataclass(frozen=True)
class PasswordResetResult:
    message: str
