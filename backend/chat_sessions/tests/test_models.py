from django.core.exceptions import ValidationError
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

    def test_chat_message_can_reference_target_output(self):
        session = Session.objects.create(owner=self.user, title="Transformasi Excel April")
        output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
        )

        message = ChatMessage.objects.create(
            session=session,
            role="user",
            content="Refine output ini.",
            target_output=output,
        )

        self.assertEqual(message.target_output, output)

    def test_chat_message_rejects_target_output_from_other_session(self):
        session = Session.objects.create(owner=self.user, title="Transformasi Excel April")
        other_session = Session.objects.create(owner=self.user, title="Other Session")
        output = GeneratedOutput.objects.create(
            session=other_session,
            output_json={"content_data": []},
        )

        message = ChatMessage(
            session=session,
            role="user",
            content="Refine output ini.",
            target_output=output,
        )

        with self.assertRaises(ValidationError):
            message.save()

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

    def test_generated_output_save_rejects_non_object_output_json(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        generated_output = GeneratedOutput(
            session=session,
            output_json=[],
        )

        with self.assertRaises(ValidationError):
            generated_output.save()

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

    def test_session_model_defines_composite_index_for_owner_and_recency(self):
        composite_index_fields = {
            tuple(index.fields)
            for index in Session._meta.indexes
        }

        self.assertIn(
            ("owner", "-last_message_at", "-updated_at", "-created_at"),
            composite_index_fields,
        )

    def test_chat_message_model_defines_index_for_session_and_created_at(self):
        index_fields = {
            tuple(index.fields)
            for index in ChatMessage._meta.indexes
        }

        self.assertIn(
            ("session", "created_at", "id"),
            index_fields,
        )

    def test_generated_output_model_defines_index_for_session_and_created_at(self):
        index_fields = {
            tuple(index.fields)
            for index in GeneratedOutput._meta.indexes
        }

        self.assertIn(
            ("session", "created_at", "id"),
            index_fields,
        )

    def test_generated_output_can_store_separate_export_output_json(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        generated_output = GeneratedOutput.objects.create(
            session=session,
            output_json={
                "headers": ["A"],
                "rows": [["1"]],
                "final_answer": "Raw output",
            },
            export_output_json={
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

        self.assertEqual(generated_output.output_json["final_answer"], "Raw output")
        self.assertEqual(
            generated_output.export_output_json["document_info"]["filename"],
            "invoice.pdf",
        )

    def test_generated_output_save_rejects_non_object_export_output_json(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        generated_output = GeneratedOutput(
            session=session,
            output_json={"headers": ["A"], "rows": [["1"]]},
            export_output_json=[],
        )

        with self.assertRaises(ValidationError):
            generated_output.save()

    def test_generated_output_can_store_thinking_log(self):
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
            thinking_log="Normalized categories and preserved totals.",
        )

        self.assertEqual(
            generated_output.thinking_log,
            "Normalized categories and preserved totals.",
        )

    def test_generated_output_can_store_reasoning_payload(self):
        session = Session.objects.create(
            owner=self.user,
            title="Transformasi Excel April",
        )

        reasoning = {
            "final_answer": "Normalization complete.",
            "reasoning_steps": ["Mapped categories", "Validated totals"],
            "thinking_log": "Normalized categories and preserved totals.",
        }
        generated_output = GeneratedOutput.objects.create(
            session=session,
            output_json={
                "document_info": {"filename": "invoice.pdf"},
                "summary": {"table_count": 1},
                "content_data": [],
            },
            reasoning=reasoning,
        )

        self.assertEqual(generated_output.reasoning, reasoning)

    def test_generated_output_can_reference_source_message_and_parent_output(self):
        session = Session.objects.create(owner=self.user, title="Transformasi Excel April")
        parent_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
        )
        source_message = ChatMessage.objects.create(
            session=session,
            role="user",
            content="Refine hasil sebelumnya.",
            target_output=parent_output,
        )

        generated_output = GeneratedOutput.objects.create(
            session=session,
            source_message=source_message,
            parent_output=parent_output,
            output_json={"content_data": []},
        )

        self.assertEqual(generated_output.source_message, source_message)
        self.assertEqual(generated_output.parent_output, parent_output)

    def test_generated_output_rejects_source_message_from_other_session(self):
        session = Session.objects.create(owner=self.user, title="Transformasi Excel April")
        other_session = Session.objects.create(owner=self.user, title="Other Session")
        source_message = ChatMessage.objects.create(
            session=other_session,
            role="user",
            content="Refine output ini.",
        )

        generated_output = GeneratedOutput(
            session=session,
            source_message=source_message,
            output_json={"content_data": []},
        )

        with self.assertRaises(ValidationError):
            generated_output.save()

    def test_generated_output_rejects_parent_output_from_other_session(self):
        session = Session.objects.create(owner=self.user, title="Transformasi Excel April")
        other_session = Session.objects.create(owner=self.user, title="Other Session")
        parent_output = GeneratedOutput.objects.create(
            session=other_session,
            output_json={"content_data": []},
        )

        generated_output = GeneratedOutput(
            session=session,
            parent_output=parent_output,
            output_json={"content_data": []},
        )

        with self.assertRaises(ValidationError):
            generated_output.save()
