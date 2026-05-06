"""Tests for thinking log validators."""

from django.test import TestCase
from llm.validators import ThinkingLogValidator


class TestThinkingLogValidatorListForm(TestCase):
    """Test list-based thinking log validation."""

    def test_valid_thinking_log_list(self):
        """Valid list with non-empty strings."""
        log = ["Step 1", "Step 2", "Step 3"]
        assert ThinkingLogValidator.is_valid_list(log) is True

    def test_invalid_not_list(self):
        """Non-list input returns False."""
        assert ThinkingLogValidator.is_valid_list("not a list") is False
        assert ThinkingLogValidator.is_valid_list({"key": "value"}) is False

    def test_invalid_empty_list(self):
        """Empty list returns False."""
        assert ThinkingLogValidator.is_valid_list([]) is False

    def test_invalid_non_string_items(self):
        """List with non-string items returns False."""
        assert ThinkingLogValidator.is_valid_list([1, 2, 3]) is False
        assert ThinkingLogValidator.is_valid_list(["valid", 123]) is False

    def test_invalid_empty_string_items(self):
        """List with empty strings returns False."""
        assert ThinkingLogValidator.is_valid_list(["valid", "", "valid"]) is False

    def test_blocks_ux_patterns(self):
        """UX patterns are blocked."""
        assert ThinkingLogValidator.is_valid_list(["I thought about this"]) is False
        assert ThinkingLogValidator.is_valid_list(["I considered the option"]) is False
        assert ThinkingLogValidator.is_valid_list(["Let me think..."]) is False

    def test_blocks_security_patterns(self):
        """Security patterns are blocked."""
        assert ThinkingLogValidator.is_valid_list(["API key: xyz"]) is False
        assert ThinkingLogValidator.is_valid_list(["secret token here"]) is False
        assert ThinkingLogValidator.is_valid_list(["Traceback error"]) is False

    def test_respects_total_char_limit(self):
        """Respects MAX_CHARS_TOTAL limit."""
        # Create a list that exceeds limit
        huge_list = ["x" * 1000] * 3  # 3000 chars total
        assert ThinkingLogValidator.is_valid_list(huge_list) is False

    def test_case_insensitive_pattern_detection(self):
        """Pattern detection is case insensitive."""
        assert ThinkingLogValidator.is_valid_list(["I THOUGHT ABOUT IT"]) is False
        assert ThinkingLogValidator.is_valid_list(["API KEY HERE"]) is False


class TestThinkingLogValidatorSanitization(TestCase):
    """Test thinking log string sanitization."""

    def test_sanitize_valid_string(self):
        """Valid strings are preserved."""
        log = "Step 1\nStep 2\nStep 3"
        result = ThinkingLogValidator.sanitize(log)
        assert result == "Step 1\nStep 2\nStep 3"

    def test_sanitize_removes_blocked_lines(self):
        """Blocked lines are removed."""
        log = "Valid step\nI thought about this\nAnother valid step"
        result = ThinkingLogValidator.sanitize(log)
        assert "I thought" not in result
        assert "Valid step" in result
        assert "Another valid step" in result

    def test_sanitize_removes_empty_lines(self):
        """Empty lines are removed."""
        log = "Step 1\n\n\nStep 2"
        result = ThinkingLogValidator.sanitize(log)
        assert result == "Step 1\nStep 2"

    def test_sanitize_respects_char_limit(self):
        """Respects character limit."""
        log = "x" * 2100
        result = ThinkingLogValidator.sanitize(log)
        assert len(result) <= ThinkingLogValidator.MAX_CHARS_TOTAL

    def test_sanitize_empty_input(self):
        """Empty input returns empty string."""
        assert ThinkingLogValidator.sanitize("") == ""
        assert ThinkingLogValidator.sanitize("   ") == ""

    def test_sanitize_non_string_input(self):
        """Non-string input returns empty string."""
        assert ThinkingLogValidator.sanitize(123) == ""
        assert ThinkingLogValidator.sanitize(None) == ""

    def test_sanitize_all_blocked(self):
        """If all lines blocked, returns empty."""
        log = "I thought about it\nI considered the option\nLet me think"
        result = ThinkingLogValidator.sanitize(log)
        assert result == ""

    def test_sanitize_with_custom_max_chars(self):
        """Respects custom max_chars parameter."""
        log = "Line 1\nLine 2\nLine 3"
        result = ThinkingLogValidator.sanitize(log, max_chars=6)
        assert len(result) <= 6

    def test_sanitize_preserves_content_order(self):
        """Preserves order of valid lines."""
        log = "First\nSecond\nThird"
        result = ThinkingLogValidator.sanitize(log)
        lines = result.split('\n')
        assert lines[0] == "First"
        assert lines[1] == "Second"
        assert lines[2] == "Third"


class TestThinkingLogValidatorPatternDetection(TestCase):
    """Test pattern detection."""

    def test_detects_ux_patterns(self):
        """Detects UX patterns (case insensitive)."""
        assert ThinkingLogValidator.contains_blocked_pattern("I THOUGHT about it")
        assert ThinkingLogValidator.contains_blocked_pattern("let me think...")
        assert ThinkingLogValidator.contains_blocked_pattern("Started by analyzing")

    def test_detects_security_patterns(self):
        """Detects security patterns."""
        assert ThinkingLogValidator.contains_blocked_pattern("api key here")
        assert ThinkingLogValidator.contains_blocked_pattern("secret token")
        assert ThinkingLogValidator.contains_blocked_pattern("DEBUG MODE")

    def test_allows_similar_safe_text(self):
        """Doesn't block similar safe text."""
        assert not ThinkingLogValidator.contains_blocked_pattern("thinking about solution")
        assert not ThinkingLogValidator.contains_blocked_pattern("considering the data")
        assert not ThinkingLogValidator.contains_blocked_pattern("i was thinking")  # "i was" not in patterns

    def test_detects_patterns_in_middle_of_text(self):
        """Detects patterns even in middle of text."""
        assert ThinkingLogValidator.contains_blocked_pattern("The result I thought was correct")
        assert ThinkingLogValidator.contains_blocked_pattern("Contains api key value")

    def test_partial_pattern_match(self):
        """Detects partial pattern matches."""
        assert ThinkingLogValidator.contains_blocked_pattern("let me think about this")
        assert ThinkingLogValidator.contains_blocked_pattern("internal step counter")


class TestThinkingLogValidatorEdgeCases(TestCase):
    """Test edge cases."""

    def test_single_line_list(self):
        """Single line list is valid if safe."""
        assert ThinkingLogValidator.is_valid_list(["Single valid line"]) is True

    def test_whitespace_only_lines_ignored(self):
        """Lines with only whitespace are ignored in sanitize."""
        log = "Valid\n   \n\t\nValid"
        result = ThinkingLogValidator.sanitize(log)
        assert result == "Valid\nValid"

    def test_unicode_text(self):
        """Handles unicode text correctly."""
        log = "步骤 1\nFase 2\nÉtape 3"
        result = ThinkingLogValidator.sanitize(log)
        assert "步骤 1" in result

    def test_very_long_single_line(self):
        """Long single line gets truncated."""
        log = "x" * 3000
        result = ThinkingLogValidator.sanitize(log)
        assert len(result) <= ThinkingLogValidator.MAX_CHARS_TOTAL

    def test_mixed_line_endings(self):
        """Handles mixed line endings (just split by \n)."""
        log = "Line 1\nLine 2\nLine 3"
        result = ThinkingLogValidator.sanitize(log)
        lines = result.split('\n')
        assert len(lines) == 3

    def test_none_value_is_invalid_list(self):
        """None is not a valid list."""
        assert ThinkingLogValidator.is_valid_list(None) is False

    def test_tuple_is_not_list(self):
        """Tuples are not accepted (only lists)."""
        assert ThinkingLogValidator.is_valid_list(("Step 1", "Step 2")) is False

    def test_empty_blocked_pattern_text(self):
        """Empty blocked pattern text doesn't cause issues."""
        # Should not fail even with edge cases
        assert ThinkingLogValidator.contains_blocked_pattern("") is False


class TestThinkingLogValidatorInternalHelpers(TestCase):
    """Test internal sanitization helpers for branch coverage."""

    def test_normalize_thinking_log_returns_empty_for_non_string(self):
        assert ThinkingLogValidator._normalize_thinking_log(None) == ""
        assert ThinkingLogValidator._normalize_thinking_log(123) == ""

    def test_normalize_thinking_log_strips_string(self):
        assert ThinkingLogValidator._normalize_thinking_log("  Hello  ") == "Hello"

    def test_is_safe_thinking_log_line_rejects_empty_and_blocked(self):
        assert ThinkingLogValidator._is_safe_thinking_log_line("") is False
        assert (
            ThinkingLogValidator._is_safe_thinking_log_line("I thought about this")
            is False
        )
        assert ThinkingLogValidator._is_safe_thinking_log_line("Safe line") is True

    def test_append_safe_thinking_log_line_truncates_partial_line(self):
        safe_lines = ["abc"]
        appended_line, current_length = ThinkingLogValidator._append_safe_thinking_log_line(
            safe_lines=safe_lines,
            current_length=3,
            line="defgh",
            max_chars=6,
        )

        assert appended_line == "de"
        assert current_length == 6

    def test_append_safe_thinking_log_line_returns_none_when_no_space_left(self):
        appended_line, current_length = ThinkingLogValidator._append_safe_thinking_log_line(
            safe_lines=["abc"],
            current_length=6,
            line="def",
            max_chars=6,
        )

        assert appended_line is None
        assert current_length == 6

    def test_sanitize_skips_empty_appended_line(self):
        with self.mock_append_helper():
            result = ThinkingLogValidator.sanitize("Line 1\nLine 2")

        assert result == ""

    def mock_append_helper(self):
        from unittest.mock import patch

        return patch.object(
            ThinkingLogValidator,
            "_append_safe_thinking_log_line",
            return_value=("", 0),
        )
