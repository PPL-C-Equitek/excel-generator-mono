"""Session history summarization operations."""

from __future__ import annotations

from typing import Any, Callable

from django.conf import settings

from llm.services.openai_client import generate_chat_response as _default_summarizer


SUMMARY_RECENT_MESSAGES_KEEP = 10
SUMMARY_REFRESH_THRESHOLD = 10


def get_summary_threshold() -> int:
    return getattr(settings, "CHAT_HISTORY_MAX_MESSAGES", 20)


def summarize_old_messages(
    messages: list[dict[str, Any]],
    summarizer: Callable[[list[dict[str, str]]], Any] | None = None,
) -> str:
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

    active_summarizer = summarizer or _default_summarizer
    result = active_summarizer([{"role": "user", "content": prompt}])
    return str(result)


def build_history_with_summary(
    session: Any,
    full_history: list[dict[str, Any]],
    *,
    summary_threshold_provider: Callable[[], int] | None = None,
    summarizer: Callable[[list[dict[str, Any]]], str] | None = None,
    recent_messages_keep: int = SUMMARY_RECENT_MESSAGES_KEEP,
    refresh_threshold: int = SUMMARY_REFRESH_THRESHOLD,
) -> list[dict[str, Any]]:
    threshold_provider = summary_threshold_provider or get_summary_threshold
    if len(full_history) <= threshold_provider():
        return full_history

    old_messages = full_history[:-recent_messages_keep]
    recent_messages = full_history[-recent_messages_keep:]

    cached_summary = session.history_summary or ""
    old_count = len(old_messages)
    summarized_watermark = session.history_summary_watermark

    active_summarizer = summarizer or summarize_old_messages
    needs_refresh = (
        not cached_summary
        or (old_count - summarized_watermark) >= refresh_threshold
    )

    if needs_refresh:
        cached_summary = active_summarizer(old_messages)
        session.history_summary = cached_summary
        session.history_summary_watermark = old_count
        session.save(
            update_fields=["history_summary", "history_summary_watermark", "updated_at"]
        )
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

