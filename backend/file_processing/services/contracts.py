"""Domain contracts for the upload validation and extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """Represents file validation outcome."""

    is_valid: bool
    error: str | None = None
    code: str | None = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def fail(cls, error: str, code: str | None = None) -> "ValidationResult":
        return cls(is_valid=False, error=error, code=code)

    def to_legacy_tuple(self) -> tuple[bool, str | None]:
        """Backwards-compatible return contract used by existing call-sites."""
        return self.is_valid, self.error


@dataclass(frozen=True)
class ExtractionResult:
    """Represents extraction/processing outcome for a validated upload."""

    success: bool
    extracted_data: Any = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        extracted_data: Any,
        warnings: list[str] | None = None,
    ) -> "ExtractionResult":
        return cls(
            success=True,
            extracted_data=extracted_data,
            warnings=warnings or [],
        )

    @classmethod
    def fail(
        cls,
        error: str,
        warnings: list[str] | None = None,
    ) -> "ExtractionResult":
        return cls(
            success=False,
            error=error,
            warnings=warnings or [],
        )

    @classmethod
    def from_legacy_tuple(
        cls,
        legacy_result: tuple[bool, str | None, Any],
    ) -> "ExtractionResult":
        """Convert legacy tuple format: ``(success, error, extracted_data)``."""
        success, error, extracted_data = legacy_result
        return cls(
            success=success,
            extracted_data=extracted_data,
            error=error,
        )

    def to_legacy_tuple(self) -> tuple[bool, str | None, Any]:
        """Backwards-compatible return contract used by existing call-sites."""
        return self.success, self.error, self.extracted_data
