"""Legacy session services.

This module remains the source of truth during the initial facade migration.
`SessionFacade` delegates to these functions in Step 1 to preserve behavior.
"""

from django.conf import settings

from llm.services.openai_client import generate_chat_response
from . import session_titles as _session_titles
from .session_queries import (
    SESSION_DETAIL_LIMIT_FIELDS,
    SESSION_DETAIL_MAX_LIMIT,
    SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
    SESSION_DETAIL_OFFSET_FIELDS,
    SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
    SESSION_LIST_DEFAULT_LIMIT,
    SESSION_LIST_MAX_LIMIT,
    build_resume_context_for_user,
    get_chat_message_for_user,
    get_default_session_detail_pagination,
    get_generated_output_for_session_user,
    get_generated_output_for_user,
    get_paginated_session_detail_for_user,
    get_session_for_user,
    list_sessions_for_user,
    validate_session_detail_pagination_params,
)
from .session_titles import resolve_session_title, sanitize_session_title
from .session_writes import (
    append_assistant_message,
    append_user_message,
    create_generated_output,
    create_session_for_user,
    delete_session,
    update_session_title,
)


# Query-related constants/functions are re-exported from session_queries
# for backward compatibility while callers are migrated incrementally.


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


def build_frontend_thinking_log_response(payload):
    reasoning_payload = _extract_reasoning_payload(payload)

    existing_thinking_log = reasoning_payload.get("thinking_log")
    if _is_valid_existing_thinking_log(existing_thinking_log):
        return {"thinking_log": list(existing_thinking_log)}

    return {"thinking_log": _build_fallback_thinking_log(reasoning_payload)}


def _extract_reasoning_payload(payload):
    if not isinstance(payload, dict):
        return {}

    reasoning_payload = payload.get("reasoning")
    if not isinstance(reasoning_payload, dict):
        return {}

    return reasoning_payload


def _is_valid_existing_thinking_log(value):
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


def _contains_blocked_thinking_log_pattern(line):
    lowered_line = line.lower()
    return any(pattern in lowered_line for pattern in _THINKING_LOG_BLOCKED_PATTERNS)


def _build_fallback_thinking_log(reasoning_payload):
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


def _normalize_reasoning_steps(value):
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        text = _normalize_text(item)
        if text:
            normalized.append(text)
    return normalized


def _normalize_text(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def _select_thinking_log_confidence(reasoning_steps, final_answer):
    if reasoning_steps and final_answer:
        return "High"
    if reasoning_steps or final_answer:
        return "Medium"
    return "Low"


def _normalize_fallback_lines(lines, confidence):
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


def generate_session_title_from_message(message, fallback="New Chat"):
    # Keep dependency injection at service boundary so existing tests that patch
    # `chat_sessions.services.generate_chat_response` stay valid.
    return _session_titles.generate_session_title_from_message(
        message,
        fallback=fallback,
        title_generator=generate_chat_response,
    )


SUMMARY_RECENT_MESSAGES_KEEP = 10

SUMMARY_REFRESH_THRESHOLD = 10


def get_summary_threshold() -> int:
    return getattr(settings, "CHAT_HISTORY_MAX_MESSAGES", 20)


def summarize_old_messages(messages: list[dict]) -> str:
    if not messages:
        return ""

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    prompt = (
        "The following is an excerpt from a conversation. "
        "Write a concise summary in English (1-2 paragraphs) that captures "
        "all key points, decisions, and context a reader would need to "
        "understand the rest of the conversation:\n\n"
        f"{transcript}"
    )
    return generate_chat_response([{"role": "user", "content": prompt}])


def build_history_with_summary(session, full_history: list[dict]) -> list[dict]:
    if len(full_history) <= get_summary_threshold():
        return full_history

    old_messages = full_history[:-SUMMARY_RECENT_MESSAGES_KEEP]
    recent_messages = full_history[-SUMMARY_RECENT_MESSAGES_KEEP:]

    cached_summary = session.history_summary or ""
    old_count = len(old_messages)
    summarized_watermark = session.history_summary_watermark

    needs_refresh = (
        not cached_summary
        or (old_count - summarized_watermark) >= SUMMARY_REFRESH_THRESHOLD
    )

    if needs_refresh:
        cached_summary = summarize_old_messages(old_messages)
        session.history_summary = cached_summary
        session.history_summary_watermark = old_count
        session.save(update_fields=["history_summary", "history_summary_watermark", "updated_at"])
    elif summarized_watermark < old_count:
        gap_messages = old_messages[summarized_watermark:]
        summary_message = {
            "role": "system",
            "content": f"[Summary of earlier conversation]: {cached_summary}",
        }
        return [summary_message] + gap_messages + recent_messages

    summary_message = {
        "role": "system",
        "content": f"[Summary of earlier conversation]: {cached_summary}",
    }
    return [summary_message] + recent_messages
