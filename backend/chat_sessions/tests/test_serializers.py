from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import serializers

from chat_sessions.serializers import (
    SessionDetailSerializer,
    SessionListItemSerializer,
    SessionTitleUpdateSerializer,
)


class ChatSessionSerializerTest(SimpleTestCase):
    def _session_stub(self):
        return SimpleNamespace(
            id="session-1",
            title="April report",
            created_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 21, 10, 5, tzinfo=timezone.utc),
            last_message_at=datetime(2026, 4, 21, 10, 4, tzinfo=timezone.utc),
            last_output_at=datetime(2026, 4, 21, 10, 5, tzinfo=timezone.utc),
            messages=[],
            generated_outputs=[],
        )

    def test_session_list_item_serializer_returns_expected_fields(self):
        serializer = SessionListItemSerializer(self._session_stub())

        self.assertEqual(serializer.data["id"], "session-1")
        self.assertEqual(serializer.data["title"], "April report")
        self.assertIn("created_at", serializer.data)
        self.assertIn("updated_at", serializer.data)
        self.assertIn("last_message_at", serializer.data)
        self.assertIn("last_output_at", serializer.data)

    def test_session_detail_serializer_includes_messages_and_outputs(self):
        session = self._session_stub()
        session.messages = [
            SimpleNamespace(
                id="message-1",
                role="user",
                content="Transform this file",
                thinking_log="",
                created_at=datetime(2026, 4, 21, 10, 1, tzinfo=timezone.utc),
            )
        ]
        session.generated_outputs = [
            SimpleNamespace(
                id="output-1",
                output_json={
                    "document_info": {"source_type": "Excel", "filename": "example.xlsx"},
                    "summary": {"total_sheets": 1, "total_rows": 2, "total_columns": 5},
                    "content_data": [],
                },
                created_at=datetime(2026, 4, 21, 10, 2, tzinfo=timezone.utc),
            )
        ]

        serializer = SessionDetailSerializer(session)

        self.assertEqual(serializer.data["id"], "session-1")
        self.assertEqual(serializer.data["messages"][0]["role"], "user")
        self.assertEqual(
            serializer.data["generated_outputs"][0]["output_json"]["document_info"]["filename"],
            "example.xlsx",
        )

    def test_session_title_update_serializer_accepts_trimmed_title(self):
        serializer = SessionTitleUpdateSerializer(data={"title": "  New Title  "})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["title"], "New Title")

    def test_session_title_update_serializer_rejects_blank_title(self):
        serializer = SessionTitleUpdateSerializer(data={"title": "   "})

        self.assertFalse(serializer.is_valid())
        self.assertIn("title", serializer.errors)

    def test_session_title_update_serializer_validate_title_rejects_whitespace_only_value(self):
        serializer = SessionTitleUpdateSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_title("   ")
