"""Validators for thinking log data and responses."""

from typing import Any


class ThinkingLogValidator:
    """Unified thinking log validation with multiple validation strategies."""

    # UX-focused patterns: user-facing narrative language to filter out
    UX_BLOCKED_PATTERNS = (
        "i thought",
        "i considered",
        "i examined",
        "started by",
        "first i think",
        "my reasoning was",
        "let me think",
        "i will analyze",
        "internal step",
    )

    # Security-focused patterns: sensitive data markers
    SECURITY_BLOCKED_PATTERNS = (
        "chain-of-thought",
        "internal prompt",
        "system prompt",
        "api key",
        "secret",
        "token",
        "debug",
        "traceback",
        "stack trace",
    )

    # Combined patterns for backward compatibility
    ALL_BLOCKED_PATTERNS = UX_BLOCKED_PATTERNS + SECURITY_BLOCKED_PATTERNS

    MAX_CHARS_TOTAL = 2000

    @classmethod
    def is_valid_list(cls, value: Any) -> bool:
        """
        Validate thinking log as a list format.

        Args:
            value: Should be list of non-empty strings with no blocked patterns

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(value, list) or len(value) < 1:
            return False

        total_chars = 0
        for line in value:
            if not isinstance(line, str):
                return False

            trimmed_line = line.strip()
            if not trimmed_line:
                return False

            if cls._contains_blocked_pattern(trimmed_line):
                return False

            total_chars += len(trimmed_line) + 1  # +1 for newline
            if total_chars > cls.MAX_CHARS_TOTAL:
                return False

        return True

    @classmethod
    def contains_blocked_pattern(cls, line: str) -> bool:
        """Check if line contains any blocked patterns.

        Args:
            line: String to check

        Returns:
            True if blocked pattern found, False otherwise
        """
        return cls._contains_blocked_pattern(line)

    @classmethod
    def sanitize(cls, log: str, max_chars: int = MAX_CHARS_TOTAL) -> str:
        """
        Remove unsafe lines from thinking log string.

        Args:
            log: Raw thinking log string
            max_chars: Maximum total characters allowed

        Returns:
            Sanitized thinking log with unsafe lines removed
        """
        normalized = cls._normalize_thinking_log(log)
        if not normalized:
            return ""

        safe_lines = []
        current_length = 0

        for line in normalized.split("\n"):
            trimmed_line = cls._normalize_thinking_log_line(line)
            if not cls._is_safe_thinking_log_line(trimmed_line):
                continue

            appended_line, current_length = cls._append_safe_thinking_log_line(
                safe_lines=safe_lines,
                current_length=current_length,
                line=trimmed_line,
                max_chars=max_chars,
            )
            if appended_line is None:
                break

            if appended_line:
                safe_lines.append(appended_line)

        return "\n".join(safe_lines) if safe_lines else ""

    @classmethod
    def _contains_blocked_pattern(cls, line: str) -> bool:
        """Internal: Check if line contains blocked patterns."""
        lowered_line = line.lower()
        return any(pattern in lowered_line for pattern in cls.ALL_BLOCKED_PATTERNS)

    @classmethod
    def _normalize_thinking_log(cls, log: str) -> str:
        if not isinstance(log, str):
            return ""

        return log.strip()

    @classmethod
    def _normalize_thinking_log_line(cls, line: str) -> str:
        return line.strip()

    @classmethod
    def _is_safe_thinking_log_line(cls, line: str) -> bool:
        return bool(line) and not cls._contains_blocked_pattern(line)

    @classmethod
    def _append_safe_thinking_log_line(
        cls,
        *,
        safe_lines: list[str],
        current_length: int,
        line: str,
        max_chars: int,
    ) -> tuple[str | None, int]:
        separator_length = 1 if safe_lines else 0
        remaining_chars = max_chars - current_length - separator_length
        if remaining_chars <= 0:
            return None, current_length

        if len(line) > remaining_chars:
            return line[:remaining_chars], max_chars

        if separator_length:
            current_length += 1

        current_length += len(line)
        return line, current_length
