from django.test import TestCase
from django.utils import timezone

from authentication.models import User
from chat_sessions.models import ChatMessage, GeneratedOutput, Session


class ChatSessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="session-owner@example.com",
            name="Session Owner",
            password="secret",
            status="verified",
        )

    def test_can_create_session_for_user(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        self.assertEqual(session.owner, self.user)
        self.assertEqual(session.title, "Transformasi Excel April")
        self.assertIsNotNone(session.created_at)
        self.assertIsNotNone(session.updated_at)

    def test_can_create_chat_message_for_session(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        message = ChatMessage.objects.create(
            session=session,
            role="user",
            content="Tolong ubah data ini ke tabel.",
        )

        self.assertEqual(message.session, session)
        self.assertEqual(message.role, "user")
        self.assertEqual(message.content, "Tolong ubah data ini ke tabel.")
        self.assertEqual(message.thinking_log, "")

    def test_can_create_generated_output_for_session(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        generated_output = GeneratedOutput.objects.create(
            session=session,
            output_json={
                "document_info": {"filename": "invoice.pdf"},
                "summary": {"table_count": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["A"],
                        "rows": [["1"]],
                    }
                ],
            },
        )

        self.assertEqual(generated_output.session, session)
        self.assertEqual(
            generated_output.output_json["document_info"]["filename"],
            "invoice.pdf",
        )
        self.assertIsNotNone(generated_output.created_at)

    def test_deleting_session_cascades_to_chat_messages(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )
        message = ChatMessage.objects.create(
            session=session,
            role="assistant",
            content="Berikut hasilnya.",
            thinking_log="Thinking summary.",
        )

        session.delete()

        self.assertFalse(ChatMessage.objects.filter(id=message.id).exists())

    def test_deleting_session_cascades_to_generated_outputs(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )
        generated_output = GeneratedOutput.objects.create(
            session=session,
            output_json={
                "document_info": {"filename": "invoice.pdf"},
                "summary": {"table_count": 1},
                "content_data": [],
            },
        )

        session.delete()

        self.assertFalse(GeneratedOutput.objects.filter(id=generated_output.id).exists())

    def test_sessions_are_ordered_by_latest_activity_fields(self):
        older = Session.objects.create(
            owner=self.user,
            title="Older Session",
            last_message_at=timezone.now() - timezone.timedelta(days=1),
        )
        newer = Session.objects.create(
            owner=self.user,
            title="Newer Session",
            last_message_at=timezone.now(),
        )

        sessions = list(Session.objects.all())

        self.assertEqual(sessions[0].id, newer.id)
        self.assertEqual(sessions[1].id, older.id)
