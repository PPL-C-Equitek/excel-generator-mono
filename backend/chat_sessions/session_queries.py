"""Read/query operations for chat session domain."""

from __future__ import annotations

from heapq import merge
from types import SimpleNamespace
from typing import Any

from django.db.models import Prefetch

from chat_sessions.models import ChatMessage, GeneratedOutput, Session


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


def list_sessions_for_user(user: Any, limit: int | None = None, offset: int = 0):
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


def get_session_for_user(user: Any, session_id: Any):
    return Session.objects.filter(owner=user, id=session_id).first()


def get_generated_output_for_session_user(user: Any, session_id: Any, output_id: Any):
    return (
        GeneratedOutput.objects.filter(
            session__owner=user,
            session_id=session_id,
            id=output_id,
        )
        .select_related("session", "source_message", "parent_output")
        .first()
    )


def get_generated_output_for_user(user: Any, output_id: Any):
    return (
        GeneratedOutput.objects.filter(
            session__owner=user,
            id=output_id,
        )
        .select_related("session", "source_message", "parent_output")
        .first()
    )


def get_chat_message_for_user(user: Any, message_id: Any):
    return (
        ChatMessage.objects.filter(
            session__owner=user,
            id=message_id,
        )
        .select_related("session", "target_output")
        .first()
    )


def get_paginated_session_detail_for_user(
    user: Any,
    session_id: Any,
    messages_limit: int = SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
    messages_offset: int = 0,
    outputs_limit: int = SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
    outputs_offset: int = 0,
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
        queryset=session.generated_outputs.select_related("source_message", "parent_output").order_by(
            "created_at",
            "id",
        ),
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


def build_resume_context_for_user(user: Any, session_id: Any):
    session = (
        Session.objects.filter(owner=user, id=session_id)
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=ChatMessage.objects.select_related("target_output").order_by("created_at", "id"),
            ),
            Prefetch(
                "generated_outputs",
                queryset=GeneratedOutput.objects.select_related("source_message", "parent_output").order_by(
                    "created_at",
                    "id",
                ),
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


def get_default_session_detail_pagination() -> dict[str, int]:
    return dict(SESSION_DETAIL_PAGINATION_DEFAULTS)


def validate_session_detail_pagination_params(pagination: dict[str, int]) -> None:
    for name in SESSION_DETAIL_LIMIT_FIELDS:
        _validate_positive_limit(name, pagination[name])
    for name in SESSION_DETAIL_OFFSET_FIELDS:
        _validate_non_negative_offset(name, pagination[name])


def _validate_positive_limit(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    if value > SESSION_DETAIL_MAX_LIMIT:
        raise ValueError(f"{name} must be less than or equal to {SESSION_DETAIL_MAX_LIMIT}.")


def _validate_non_negative_offset(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be greater than or equal to 0.")


def _build_paginated_collection(queryset: Any, limit: int, offset: int) -> dict[str, Any]:
    return {
        "count": queryset.count(),
        "limit": limit,
        "offset": offset,
        "results": list(queryset[offset : offset + limit]),
    }


def _build_resume_history(session: Any):
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

