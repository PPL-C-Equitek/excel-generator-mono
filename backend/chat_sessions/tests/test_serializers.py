from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import serializers

from chat_sessions.serializers import (
    PaginatedGeneratedOutputCollectionSerializer,
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
        session.messages = {
            "count": 1,
            "limit": 20,
            "offset": 0,
            "results": [
                SimpleNamespace(
                    id="message-1",
                    role="user",
                    content="Transform this file",
                    thinking_log="",
                    created_at=datetime(2026, 4, 21, 10, 1, tzinfo=timezone.utc),
                )
            ],
        }
        session.generated_outputs = {
            "count": 1,
            "limit": 10,
            "offset": 0,
            "results": [
                SimpleNamespace(
                    id="output-1",
                    output_json={
                        "document_info": {"source_type": "Excel", "filename": "example.xlsx"},
                        "summary": {"total_sheets": 1, "total_rows": 2, "total_columns": 5},
                        "content_data": [],
                    },
                    created_at=datetime(2026, 4, 21, 10, 2, tzinfo=timezone.utc),
                )
            ],
        }

        serializer = SessionDetailSerializer(session)

        self.assertEqual(serializer.data["id"], "session-1")
        self.assertEqual(serializer.data["messages"]["results"][0]["role"], "user")
        self.assertEqual(
            serializer.data["generated_outputs"]["results"][0]["output_json"]["document_info"]["filename"],
            "example.xlsx",
        )

    def test_session_detail_serializer_returns_paginated_messages_and_outputs(self):
        session = self._session_stub()
        session.messages = {
            "count": 2,
            "limit": 1,
            "offset": 1,
            "results": [
                SimpleNamespace(
                    id="message-2",
                    role="assistant",
                    content="Here is the result",
                    thinking_log="Reasoning summary",
                    created_at=datetime(2026, 4, 21, 10, 3, tzinfo=timezone.utc),
                )
            ],
        }
        session.generated_outputs = {
            "count": 1,
            "limit": 10,
            "offset": 0,
            "results": [
                SimpleNamespace(
                    id="output-1",
                    output_json={
                        "document_info": {"source_type": "Excel", "filename": "example.xlsx"},
                        "summary": {"total_sheets": 1, "total_rows": 2, "total_columns": 5},
                        "content_data": [],
                    },
                    created_at=datetime(2026, 4, 21, 10, 4, tzinfo=timezone.utc),
                )
            ],
        }

        serializer = SessionDetailSerializer(session)

        self.assertEqual(serializer.data["messages"]["count"], 2)
        self.assertEqual(serializer.data["messages"]["limit"], 1)
        self.assertEqual(serializer.data["messages"]["offset"], 1)
        self.assertEqual(serializer.data["messages"]["results"][0]["role"], "assistant")
        self.assertEqual(serializer.data["generated_outputs"]["count"], 1)
        self.assertEqual(
            serializer.data["generated_outputs"]["results"][0]["output_json"]["document_info"]["filename"],
            "example.xlsx",
        )

    def test_session_detail_serializer_supports_empty_paginated_collections(self):
        session = self._session_stub()
        session.messages = {"count": 0, "limit": 20, "offset": 0, "results": []}
        session.generated_outputs = {"count": 0, "limit": 10, "offset": 0, "results": []}

        serializer = SessionDetailSerializer(session)

        self.assertEqual(serializer.data["messages"], {"count": 0, "limit": 20, "offset": 0, "results": []})
        self.assertEqual(
            serializer.data["generated_outputs"],
            {"count": 0, "limit": 10, "offset": 0, "results": []},
        )

    def test_paginated_generated_output_collection_serializer_rejects_missing_results(self):
        serializer = PaginatedGeneratedOutputCollectionSerializer(
            data={"count": 1, "limit": 10, "offset": 0}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("results", serializer.errors)

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
