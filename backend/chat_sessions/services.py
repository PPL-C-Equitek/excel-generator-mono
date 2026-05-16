import re
from heapq import merge
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from llm.services.openai_client import generate_chat_response


SESSION_LIST_MAX_LIMIT = 50
SESSION_LIST_DEFAULT_LIMIT = 10
SESSION_DETAIL_MAX_LIMIT = 50
SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT = 20
SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT = 10
SESSION_DETAIL_PAGINATION_DEFAULTS = {
    "messages_limit": SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
    "messages_offset": 0,
    "outputs_limit": SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
    "outputs_offset": 0,
}
SESSION_DETAIL_LIMIT_FIELDS = ("messages_limit", "outputs_limit")
SESSION_DETAIL_OFFSET_FIELDS = ("messages_offset", "outputs_offset")
SESSION_LIST_FIELDS = (
    "id",
    "title",
    "created_at",
    "updated_at",
    "last_message_at",
    "last_output_at",
    "history_summary",
    "history_summary_watermark",
)


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


def create_session_for_user(owner, title=""):
    return Session.objects.create(
        owner=owner,
        title=(title or "").strip(),
    )


def list_sessions_for_user(user, limit=None, offset=0):
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0.")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than 0.")
    if limit is not None and limit > SESSION_LIST_MAX_LIMIT:
        raise ValueError(f"limit must be less than or equal to {SESSION_LIST_MAX_LIMIT}.")

    queryset = Session.objects.filter(owner=user).only(*SESSION_LIST_FIELDS)
    if limit is None:
        return queryset
    return queryset[offset : offset + limit]


def get_session_for_user(user, session_id):
    return Session.objects.filter(owner=user, id=session_id).first()


def get_generated_output_for_session_user(user, session_id, output_id):
    return (
        GeneratedOutput.objects.filter(
            session__owner=user,
            session_id=session_id,
            id=output_id,
        )
        .select_related("session", "source_message", "parent_output")
        .first()
    )


def get_generated_output_for_user(user, output_id):
    return (
        GeneratedOutput.objects.filter(
            session__owner=user,
            id=output_id,
        )
        .select_related("session", "source_message", "parent_output")
        .first()
    )


def get_chat_message_for_user(user, message_id):
    return (
        ChatMessage.objects.filter(
            session__owner=user,
            id=message_id,
        )
        .select_related("session", "target_output")
        .first()
    )


def get_paginated_session_detail_for_user(
    user,
    session_id,
    messages_limit=SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
    messages_offset=0,
    outputs_limit=SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
    outputs_offset=0,
):
    validate_session_detail_pagination_params(
        {
            "messages_limit": messages_limit,
            "messages_offset": messages_offset,
            "outputs_limit": outputs_limit,
            "outputs_offset": outputs_offset,
        }
    )
    session = get_session_for_user(user, session_id)
    if session is None:
        return None

    messages = _build_paginated_collection(
        queryset=session.messages.select_related("target_output").order_by("created_at", "id"),
        limit=messages_limit,
        offset=messages_offset,
    )
    generated_outputs = _build_paginated_collection(
        queryset=session.generated_outputs.select_related("source_message", "parent_output").order_by("created_at", "id"),
        limit=outputs_limit,
        offset=outputs_offset,
    )

    return SimpleNamespace(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_at=session.last_message_at,
        last_output_at=session.last_output_at,
        messages=messages,
        generated_outputs=generated_outputs,
    )


def build_resume_context_for_user(user, session_id):
    session = (
        Session.objects.filter(owner=user, id=session_id)
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=ChatMessage.objects.select_related("target_output").order_by("created_at", "id"),
            ),
            Prefetch(
                "generated_outputs",
                queryset=GeneratedOutput.objects.select_related("source_message", "parent_output").order_by("created_at", "id"),
            ),
        )
        .first()
    )
    if session is None:
        return None

    history = _build_resume_history(session)

    return SimpleNamespace(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_at=session.last_message_at,
        last_output_at=session.last_output_at,
        history=history,
    )


def get_default_session_detail_pagination():
    return dict(SESSION_DETAIL_PAGINATION_DEFAULTS)


def validate_session_detail_pagination_params(pagination):
    for name in SESSION_DETAIL_LIMIT_FIELDS:
        _validate_positive_limit(name, pagination[name])
    for name in SESSION_DETAIL_OFFSET_FIELDS:
        _validate_non_negative_offset(name, pagination[name])


def _validate_positive_limit(name, value):
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    if value > SESSION_DETAIL_MAX_LIMIT:
        raise ValueError(f"{name} must be less than or equal to {SESSION_DETAIL_MAX_LIMIT}.")


def _validate_non_negative_offset(name, value):
    if value < 0:
        raise ValueError(f"{name} must be greater than or equal to 0.")


def _build_paginated_collection(queryset, limit, offset):
    return {
        "count": queryset.count(),
        "limit": limit,
        "offset": offset,
        "results": list(queryset[offset : offset + limit]),
    }


def _build_resume_history(session):
    message_items = (
        SimpleNamespace(
            type="message",
            id=message.id,
            role=message.role,
            content=message.content,
            thinking_log=message.thinking_log or "",
            target_output_id=message.target_output_id,
            created_at=message.created_at,
        )
        for message in session.messages.all()
    )
    output_items = (
        SimpleNamespace(
            type="output",
            id=output.id,
            source_message_id=output.source_message_id,
            parent_output_id=output.parent_output_id,
            output_json=output.output_json,
            thinking_log=output.thinking_log or "",
            reasoning=output.reasoning or {},
            created_at=output.created_at,
        )
        for output in session.generated_outputs.all()
    )

    return list(
        merge(
            message_items,
            output_items,
            key=lambda item: (item.created_at, str(item.id)),
        )
    )


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def sanitize_session_title(title):
    if not title:
        return ""

    stripped = title.strip()
    if not stripped:
        return ""

    normalized = re.sub(r"[\r\n\t]", " ", stripped)

    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()

    return normalized[:120]


def resolve_session_title(candidate_title, fallback="New Chat"):
    sanitized = sanitize_session_title(candidate_title)
    if not sanitized:
        return fallback
    return sanitized


def generate_session_title_from_message(message, fallback="New Chat"):
    if not message or not message.strip():
        return fallback

    title_prompt = (
        "Berikan judul singkat maksimal 3-5 kata untuk chat berikut. "
        "Abaikan sapaan, ambil konteks utama. Jangan gunakan karakter newline, "
        f"cukup 1 kalimat: {message}"
    )

    try:
        title_suggestion = generate_chat_response(
            [{"role": "user", "content": title_prompt}]
        )
    except Exception:
        return fallback

    return resolve_session_title(title_suggestion, fallback=fallback)


def delete_session(session):
    session.delete()


def append_user_message(session, content, target_output=None):
    now = timezone.now()
    msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content=content,
        target_output=target_output,
    )
    session.last_message_at = now
    session.save(update_fields=["last_message_at", "updated_at"])
    return msg


def append_assistant_message(session, content, thinking_log=None):
    now = timezone.now()
    msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_ASSISTANT,
        content=content,
        thinking_log=thinking_log or "",
    )
    session.last_message_at = now
    session.save(update_fields=["last_message_at", "updated_at"])
    return msg


def create_generated_output(
    session,
    output_json,
    thinking_log="",
    export_output_json=None,
    reasoning=None,
    source_message=None,
    parent_output=None,
):
    now = timezone.now()
    # Temporary compatibility shim while callers are migrated away from
    # export_output_json-as-third-positional-arg.
    if export_output_json is None and isinstance(thinking_log, dict):
        export_output_json = thinking_log
        thinking_log = ""

    output = GeneratedOutput.objects.create(
        session=session,
        source_message=source_message,
        parent_output=parent_output,
        output_json=output_json,
        thinking_log=thinking_log or "",
        reasoning=reasoning if isinstance(reasoning, dict) else {},
        export_output_json=export_output_json or {},
    )
    session.last_output_at = now
    session.save(update_fields=["last_output_at", "updated_at"])
    return output


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


def _build_summary_message(summary: str) -> dict[str, str]:
    return {
        "role": "system",
        "content": f"[Summary of earlier conversation]: {summary}",
    }


def _normalize_summary_watermark(value) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized >= 0 else 0


def _reload_persisted_summary_state(session) -> tuple[str, int]:
    persisted_state = (
        Session.objects.filter(id=session.id)
        .values("history_summary", "history_summary_watermark")
        .first()
    )
    if persisted_state is None:
        return "", 0
    return (
        persisted_state.get("history_summary") or "",
        _normalize_summary_watermark(persisted_state.get("history_summary_watermark")),
    )


def _persist_summary_if_unchanged(
    session,
    expected_summary: str,
    expected_watermark: int,
    new_summary: str,
    new_watermark: int,
) -> bool:
    updated_rows = Session.objects.filter(
        id=session.id,
        history_summary=expected_summary,
        history_summary_watermark=expected_watermark,
    ).update(
        history_summary=new_summary,
        history_summary_watermark=new_watermark,
        updated_at=timezone.now(),
    )
    if updated_rows:
        session.history_summary = new_summary
        session.history_summary_watermark = new_watermark
        return True
    return False


def build_history_with_summary(session, full_history: list[dict]) -> list[dict]:
    if len(full_history) <= get_summary_threshold():
        return full_history

    old_messages = full_history[:-SUMMARY_RECENT_MESSAGES_KEEP]
    recent_messages = full_history[-SUMMARY_RECENT_MESSAGES_KEEP:]

    cached_summary = session.history_summary or ""
    old_count = len(old_messages)
    summarized_watermark = _normalize_summary_watermark(session.history_summary_watermark)

    needs_refresh = (
        not cached_summary
        or (old_count - summarized_watermark) >= SUMMARY_REFRESH_THRESHOLD
    )

    if needs_refresh:
        refreshed_summary = summarize_old_messages(old_messages)
        persisted = _persist_summary_if_unchanged(
            session=session,
            expected_summary=cached_summary,
            expected_watermark=summarized_watermark,
            new_summary=refreshed_summary,
            new_watermark=old_count,
        )
        if persisted:
            cached_summary = refreshed_summary
            summarized_watermark = old_count
        else:
            cached_summary, summarized_watermark = _reload_persisted_summary_state(session)
            if not cached_summary:
                cached_summary = refreshed_summary
                summarized_watermark = old_count

    summary_message = _build_summary_message(cached_summary)
    if summarized_watermark < old_count:
        gap_messages = old_messages[summarized_watermark:]
        return [summary_message] + gap_messages + recent_messages
    return [summary_message] + recent_messages
