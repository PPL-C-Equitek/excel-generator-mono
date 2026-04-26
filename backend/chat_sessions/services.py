from django.conf import settings
from django.utils import timezone

from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from llm.services.openai_client import generate_chat_response


SESSION_LIST_MAX_LIMIT = 50
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


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


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


def create_generated_output(session, output_json):
    now = timezone.now()
    output = GeneratedOutput.objects.create(
        session=session,
        output_json=output_json,
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
