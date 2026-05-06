"""Legacy session services.

This module remains the source of truth during the initial facade migration.
`SessionFacade` delegates to these functions in Step 1 to preserve behavior.
"""

from llm.services.openai_client import generate_chat_response
from . import session_history as _session_history
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
from .session_history import SUMMARY_RECENT_MESSAGES_KEEP, SUMMARY_REFRESH_THRESHOLD
from .session_titles import resolve_session_title, sanitize_session_title
from .session_writes import (
    append_assistant_message,
    append_user_message,
    create_generated_output,
    create_session_for_user,
    delete_session,
    update_session_title,
)
from .thinking_log import (
    _FAIL_SAFE_THINKING_LOG,
    _THINKING_LOG_BLOCKED_PATTERNS,
    _build_fallback_thinking_log,
    _contains_blocked_thinking_log_pattern,
    _extract_reasoning_payload,
    _is_valid_existing_thinking_log,
    _normalize_fallback_lines,
    _normalize_reasoning_steps,
    _normalize_text,
    _select_thinking_log_confidence,
    build_frontend_thinking_log_response,
)


__all__ = [
    "SESSION_DETAIL_LIMIT_FIELDS",
    "SESSION_DETAIL_MAX_LIMIT",
    "SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT",
    "SESSION_DETAIL_OFFSET_FIELDS",
    "SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT",
    "SESSION_LIST_DEFAULT_LIMIT",
    "SESSION_LIST_MAX_LIMIT",
    "SUMMARY_RECENT_MESSAGES_KEEP",
    "SUMMARY_REFRESH_THRESHOLD",
    "_FAIL_SAFE_THINKING_LOG",
    "_THINKING_LOG_BLOCKED_PATTERNS",
    "_build_fallback_thinking_log",
    "_contains_blocked_thinking_log_pattern",
    "_extract_reasoning_payload",
    "_is_valid_existing_thinking_log",
    "_normalize_fallback_lines",
    "_normalize_reasoning_steps",
    "_normalize_text",
    "_select_thinking_log_confidence",
    "append_assistant_message",
    "append_user_message",
    "build_frontend_thinking_log_response",
    "build_history_with_summary",
    "build_resume_context_for_user",
    "create_generated_output",
    "create_session_for_user",
    "delete_session",
    "generate_session_title_from_message",
    "get_chat_message_for_user",
    "get_default_session_detail_pagination",
    "get_generated_output_for_session_user",
    "get_generated_output_for_user",
    "get_paginated_session_detail_for_user",
    "get_session_for_user",
    "get_summary_threshold",
    "list_sessions_for_user",
    "resolve_session_title",
    "sanitize_session_title",
    "summarize_old_messages",
    "update_session_title",
    "validate_session_detail_pagination_params",
]


def generate_session_title_from_message(message, fallback="New Chat"):
    # Keep dependency injection at service boundary so existing tests that patch
    # `chat_sessions.services.generate_chat_response` stay valid.
    return _session_titles.generate_session_title_from_message(
        message,
        fallback=fallback,
        title_generator=generate_chat_response,
    )


def get_summary_threshold() -> int:
    return _session_history.get_summary_threshold()


def summarize_old_messages(messages: list[dict]) -> str:
    # Keep dependency injection at service boundary so existing tests that patch
    # `chat_sessions.services.generate_chat_response` stay valid.
    return _session_history.summarize_old_messages(
        messages,
        summarizer=generate_chat_response,
    )


def build_history_with_summary(session, full_history: list[dict]) -> list[dict]:
    # Keep dependency injection at service boundary so existing tests that patch
    # `chat_sessions.services.summarize_old_messages` stay valid.
    return _session_history.build_history_with_summary(
        session,
        full_history,
        summary_threshold_provider=get_summary_threshold,
        summarizer=summarize_old_messages,
        recent_messages_keep=SUMMARY_RECENT_MESSAGES_KEEP,
        refresh_threshold=SUMMARY_REFRESH_THRESHOLD,
    )
