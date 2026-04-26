from types import SimpleNamespace

from django.conf import settings
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
        .select_related("session")
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
        queryset=session.messages.order_by("created_at", "id"),
        limit=messages_limit,
        offset=messages_offset,
    )
    generated_outputs = _build_paginated_collection(
        queryset=session.generated_outputs.order_by("created_at", "id"),
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
    session = get_session_for_user(user, session_id)
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
    message_items = [
        SimpleNamespace(
            type="message",
            id=message.id,
            role=message.role,
            content=message.content,
            thinking_log=message.thinking_log,
            created_at=message.created_at,
        )
        for message in session.messages.order_by("created_at", "id")
    ]
    output_items = [
        SimpleNamespace(
            type="output",
            id=output.id,
            output_json=output.output_json,
            thinking_log=output.thinking_log,
            created_at=output.created_at,
        )
        for output in session.generated_outputs.order_by("created_at", "id")
    ]

    return sorted(
        [*message_items, *output_items],
        key=lambda item: (item.created_at, str(item.id)),
    )


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def sanitize_session_title(title):
    if not title or not title.strip():
        return ""
    
    normalized = title.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
    return normalized[:120]


def resolve_session_title(candidate_title, fallback="New Chat"):
    sanitized = sanitize_session_title(candidate_title)
    if not sanitized:
        return fallback
    return sanitized


def delete_session(session):
    session.delete()


def append_user_message(session, content):
    now = timezone.now()
    msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content=content,
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
):
    now = timezone.now()
    # Temporary compatibility shim while callers are migrated away from
    # export_output_json-as-third-positional-arg.
    if export_output_json is None and isinstance(thinking_log, dict):
        export_output_json = thinking_log
        thinking_log = ""

    output = GeneratedOutput.objects.create(
        session=session,
        output_json=output_json,
        thinking_log=thinking_log or "",
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
