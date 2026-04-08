from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    refresh_token: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "refresh_token", self.refresh_token.strip())
