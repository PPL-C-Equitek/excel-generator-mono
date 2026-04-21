from chat_sessions.models import Session


def create_session_for_user(owner, title=""):
    return Session.objects.create(
        owner=owner,
        title=(title or "").strip(),
    )


def list_sessions_for_user(user):
    return Session.objects.filter(owner=user)


def get_session_for_user(user, session_id):
    return Session.objects.filter(owner=user, id=session_id).first()


def update_session_title(session, title):
    session.title = (title or "").strip()
    session.save(update_fields=["title", "updated_at"])
    return session


def delete_session(session):
    session.delete()
