"""Write/mutation operations for chat session domain."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from chat_sessions.models import ChatMessage, GeneratedOutput, Session


def create_session_for_user(owner: Any, title: str = ""):
    return Session.objects.create(
        owner=owner,
        title=(title or "").strip(),
    )


def update_session_title(session: Any, title: str):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def delete_session(session: Any) -> None:
    session.delete()


def append_user_message(session: Any, content: str, target_output: Any = None):
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


def append_assistant_message(session: Any, content: str, thinking_log: str | None = None):
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
    session: Any,
    output_json: Any,
    thinking_log: str = "",
    export_output_json: dict[str, Any] | None = None,
    reasoning: dict[str, Any] | None = None,
    source_message: Any = None,
    parent_output: Any = None,
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

