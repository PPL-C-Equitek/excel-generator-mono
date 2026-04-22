from types import SimpleNamespace

from chat_sessions.models import Session


SESSION_LIST_MAX_LIMIT = 50
SESSION_DETAIL_MAX_LIMIT = 50
SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT = 20
SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT = 10
SESSION_LIST_FIELDS = (
    "id",
    "title",
    "created_at",
    "updated_at",
    "last_message_at",
    "last_output_at",
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


def get_paginated_session_detail_for_user(
    user,
    session_id,
    messages_limit=SESSION_DETAIL_MESSAGES_DEFAULT_LIMIT,
    messages_offset=0,
    outputs_limit=SESSION_DETAIL_OUTPUTS_DEFAULT_LIMIT,
    outputs_offset=0,
):
    _validate_session_detail_pagination(
        messages_limit=messages_limit,
        messages_offset=messages_offset,
        outputs_limit=outputs_limit,
        outputs_offset=outputs_offset,
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


def _validate_session_detail_pagination(
    messages_limit,
    messages_offset,
    outputs_limit,
    outputs_offset,
):
    _validate_positive_limit("messages_limit", messages_limit)
    _validate_positive_limit("outputs_limit", outputs_limit)
    _validate_non_negative_offset("messages_offset", messages_offset)
    _validate_non_negative_offset("outputs_offset", outputs_offset)


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


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def delete_session(session):
    session.delete()
