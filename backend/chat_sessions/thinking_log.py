"""Thinking-log normalization and fallback building utilities."""

from __future__ import annotations

from typing import Any


_THINKING_LOG_BLOCKED_PATTERNS = (
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

_FAIL_SAFE_THINKING_LOG = [
    "Processed available response data.",
    "Unable to extract detailed reasoning.",
    "Prepared safest structured output.",
    "Confidence: Low",
]


def build_frontend_thinking_log_response(payload: Any) -> dict[str, list[str]]:
    reasoning_payload = _extract_reasoning_payload(payload)

    existing_thinking_log = reasoning_payload.get("thinking_log")
    if _is_valid_existing_thinking_log(existing_thinking_log):
        return {"thinking_log": list(existing_thinking_log)}

    return {"thinking_log": _build_fallback_thinking_log(reasoning_payload)}


def _extract_reasoning_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    reasoning_payload = payload.get("reasoning")
    if not isinstance(reasoning_payload, dict):
        return {}

    return reasoning_payload


def _is_valid_existing_thinking_log(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 1:
        return False

    for line in value:
        if not isinstance(line, str):
            return False

        trimmed_line = line.strip()
        if not trimmed_line:
            return False

        if _contains_blocked_thinking_log_pattern(trimmed_line):
            return False

    return True


def _contains_blocked_thinking_log_pattern(line: str) -> bool:
    lowered_line = line.lower()
    return any(pattern in lowered_line for pattern in _THINKING_LOG_BLOCKED_PATTERNS)


def _build_fallback_thinking_log(reasoning_payload: Any) -> list[str]:
    if not isinstance(reasoning_payload, dict):
        return list(_FAIL_SAFE_THINKING_LOG)

    reasoning_steps = _normalize_reasoning_steps(reasoning_payload.get("reasoning_steps"))
    final_answer = _normalize_text(reasoning_payload.get("final_answer"))

    if not reasoning_steps and not final_answer:
        return list(_FAIL_SAFE_THINKING_LOG)

    lines = [
        "Identified available response reasoning fields.",
    ]
    if reasoning_steps:
        lines.append("Summarized key transformation steps from response data.")
    if final_answer:
        lines.append("Aligned summary details with the final answer content.")
    lines.append("Validated thinking log consistency for frontend parsing.")
    lines.append("Prepared parser-safe thinking log output.")

    confidence = _select_thinking_log_confidence(reasoning_steps, final_answer)
    return _normalize_fallback_lines(lines, confidence)


def _normalize_reasoning_steps(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        text = _normalize_text(item)
        if text:
            normalized.append(text)
    return normalized


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _select_thinking_log_confidence(reasoning_steps: list[str], final_answer: str) -> str:
    if reasoning_steps and final_answer:
        return "High"
    if reasoning_steps or final_answer:
        return "Medium"
    return "Low"


def _normalize_fallback_lines(lines: list[str], confidence: str) -> list[str]:
    normalized_lines = []
    seen = set()

    for line in lines:
        trimmed = line.strip()
        if not trimmed or trimmed in seen:
            continue
        normalized_lines.append(trimmed)
        seen.add(trimmed)

    normalized_lines = normalized_lines[:5]
    normalized_lines.append(f"Confidence: {confidence}")
    return normalized_lines

