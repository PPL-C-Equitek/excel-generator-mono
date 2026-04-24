from django.test import TestCase

from authentication.models import User
from chat_sessions.models import Session
from chat_sessions.services import (
    create_session_for_user,
    delete_session,
    get_session_for_user,
    list_sessions_for_user,
    update_session_title,
)


class ChatSessionServiceTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-services@example.com",
            name="Owner Services",
            password="secret",
            status="verified",
        )
        self.other_user = User.objects.create_user(
            email="other-services@example.com",
            name="Other Services",
            password="secret",
            status="verified",
        )

    def test_create_session_for_user_creates_session_with_default_title(self):
        session = create_session_for_user(self.owner)

        self.assertEqual(session.owner, self.owner)
        self.assertEqual(session.title, "")
        self.assertTrue(Session.objects.filter(id=session.id).exists())

    def test_list_sessions_for_user_returns_only_owned_sessions(self):
        owned_older = Session.objects.create(
            owner=self.owner,
            title="Owned Older",
        )
        owned_newer = Session.objects.create(
            owner=self.owner,
            title="Owned Newer",
        )
        Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )

        sessions = list(list_sessions_for_user(self.owner))

        self.assertEqual([session.id for session in sessions], [owned_newer.id, owned_older.id])

    def test_list_sessions_for_user_applies_limit_and_offset(self):
        owned_oldest = Session.objects.create(
            owner=self.owner,
            title="Owned Oldest",
        )
        owned_middle = Session.objects.create(
            owner=self.owner,
            title="Owned Middle",
        )
        owned_newest = Session.objects.create(
            owner=self.owner,
            title="Owned Newest",
        )

        sessions = list(list_sessions_for_user(self.owner, limit=1, offset=1))

        self.assertEqual([session.id for session in sessions], [owned_middle.id])
        self.assertNotIn(owned_newest.id, [session.id for session in sessions])
        self.assertNotIn(owned_oldest.id, [session.id for session in sessions])

    def test_list_sessions_for_user_rejects_non_positive_limit(self):
        with self.assertRaisesMessage(ValueError, "limit must be greater than 0."):
            list(list_sessions_for_user(self.owner, limit=0, offset=0))

    def test_list_sessions_for_user_rejects_negative_offset(self):
        with self.assertRaisesMessage(ValueError, "offset must be greater than or equal to 0."):
            list(list_sessions_for_user(self.owner, limit=10, offset=-1))

    def test_list_sessions_for_user_rejects_limit_above_maximum(self):
        with self.assertRaisesMessage(ValueError, "limit must be less than or equal to 50."):
            list(list_sessions_for_user(self.owner, limit=51, offset=0))

    def test_list_sessions_for_user_defers_unused_fields_for_list_view(self):
        Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        session = list(list_sessions_for_user(self.owner, limit=10, offset=0))[0]

        self.assertSetEqual(session.get_deferred_fields(), {"owner_id"})

    def test_get_session_for_user_returns_owned_session(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        result = get_session_for_user(self.owner, session.id)

        self.assertEqual(result, session)

    def test_get_session_for_user_returns_none_for_non_owned_session(self):
        session = Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )

        result = get_session_for_user(self.owner, session.id)

        self.assertIsNone(result)

    def test_update_session_title_trims_and_saves_value(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Old Title",
        )

        updated = update_session_title(session, "  New Session Title  ")

        self.assertEqual(updated.title, "New Session Title")
        session.refresh_from_db()
        self.assertEqual(session.title, "New Session Title")

    def test_delete_session_removes_session(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Session To Delete",
        )

        delete_session(session)

        self.assertFalse(Session.objects.filter(id=session.id).exists())
