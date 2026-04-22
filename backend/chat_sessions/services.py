from chat_sessions.models import Session


SESSION_LIST_MAX_LIMIT = 50
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


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def delete_session(session):
    session.delete()
