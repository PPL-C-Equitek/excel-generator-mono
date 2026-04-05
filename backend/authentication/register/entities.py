from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisterCommand:
    name: str
    email: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", self.email.lower().strip())


@dataclass(frozen=True, slots=True)
class RegistrationUser:
    email: str
    status: str


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    message: str
