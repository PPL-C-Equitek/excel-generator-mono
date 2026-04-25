from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import User
from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from chat_sessions.services import (
    append_assistant_message,
    append_user_message,
    create_generated_output,
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


class AppendUserMessageServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="append-user@example.com",
            name="Append User",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)

    def test_append_user_message_creates_message_with_user_role(self):
        msg = append_user_message(self.session, "Halo")

        self.assertEqual(msg.role, ChatMessage.ROLE_USER)
        self.assertEqual(msg.content, "Halo")
        self.assertEqual(msg.session, self.session)

    def test_append_user_message_persists_to_db(self):
        msg = append_user_message(self.session, "Halo")

        self.assertTrue(ChatMessage.objects.filter(id=msg.id).exists())

    def test_append_user_message_thinking_log_is_empty_by_default(self):
        msg = append_user_message(self.session, "Halo")

        self.assertEqual(msg.thinking_log, "")

    def test_append_user_message_updates_session_last_message_at(self):
        self.assertIsNone(self.session.last_message_at)

        append_user_message(self.session, "Halo")

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_message_at)


class AppendAssistantMessageServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="append-assistant@example.com",
            name="Append Assistant",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)

    def test_append_assistant_message_creates_message_with_assistant_role(self):
        msg = append_assistant_message(self.session, "Berikut jawabannya.")

        self.assertEqual(msg.role, ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(msg.content, "Berikut jawabannya.")
        self.assertEqual(msg.session, self.session)

    def test_append_assistant_message_persists_to_db(self):
        msg = append_assistant_message(self.session, "Berikut jawabannya.")

        self.assertTrue(ChatMessage.objects.filter(id=msg.id).exists())

    def test_append_assistant_message_stores_thinking_log_when_provided(self):
        msg = append_assistant_message(
            self.session, "Jawaban.", thinking_log="langkah berpikir"
        )

        self.assertEqual(msg.thinking_log, "langkah berpikir")

    def test_append_assistant_message_thinking_log_defaults_to_empty(self):
        msg = append_assistant_message(self.session, "Jawaban.")

        self.assertEqual(msg.thinking_log, "")

    def test_append_assistant_message_updates_session_last_message_at(self):
        self.assertIsNone(self.session.last_message_at)

        append_assistant_message(self.session, "Berikut jawabannya.")

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_message_at)


class CreateGeneratedOutputServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="gen-output@example.com",
            name="Gen Output",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)
        self.valid_output_json = {
            "document_info": {"filename": "test.xlsx"},
            "summary": {"total_sheets": 1},
            "content_data": [],
        }

    def test_create_generated_output_creates_output_with_correct_data(self):
        output = create_generated_output(self.session, self.valid_output_json)

        self.assertEqual(output.output_json, self.valid_output_json)
        self.assertEqual(output.session, self.session)

    def test_create_generated_output_persists_to_db(self):
        output = create_generated_output(self.session, self.valid_output_json)

        self.assertTrue(GeneratedOutput.objects.filter(id=output.id).exists())

    def test_create_generated_output_updates_session_last_output_at(self):
        self.assertIsNone(self.session.last_output_at)

        create_generated_output(self.session, self.valid_output_json)

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_output_at)

    def test_create_generated_output_rejects_non_dict_output_json(self):
        with self.assertRaises(ValidationError):
            create_generated_output(self.session, ["bukan", "dict"])
