from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import serializers

from chat_sessions.serializers import (
    PaginatedChatMessageCollectionSerializer,
    PaginatedCollectionSerializer,
    PaginatedGeneratedOutputCollectionSerializer,
    ResumeHistoryItemSerializer,
    SessionResumeSerializer,
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
                    thinking_log="Normalized columns and preserved totals.",
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
        self.assertEqual(
            serializer.data["generated_outputs"]["results"][0]["thinking_log"],
            "Normalized columns and preserved totals.",
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
                    thinking_log="Kept row grouping stable.",
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
        self.assertEqual(
            serializer.data["generated_outputs"]["results"][0]["thinking_log"],
            "Kept row grouping stable.",
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

    def test_session_resume_serializer_includes_chat_history_and_thinking_logs(self):
        session = self._session_stub()
        session.history = [
            SimpleNamespace(
                type="message",
                id="message-1",
                role="assistant",
                content="Here is the summary.",
                thinking_log="Grouped expense rows before answering.",
                created_at=datetime(2026, 4, 21, 10, 3, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                type="output",
                id="output-1",
                output_json={
                    "document_info": {"source_type": "Excel", "filename": "example.xlsx"},
                    "summary": {"total_sheets": 1, "total_rows": 2, "total_columns": 5},
                    "content_data": [],
                },
                thinking_log="Normalized columns and preserved totals.",
                created_at=datetime(2026, 4, 21, 10, 4, tzinfo=timezone.utc),
            ),
        ]

        serializer = SessionResumeSerializer(session)

        self.assertEqual(serializer.data["id"], "session-1")
        self.assertEqual(len(serializer.data["history"]), 2)
        self.assertEqual(serializer.data["history"][0]["type"], "message")
        self.assertEqual(serializer.data["history"][0]["role"], "assistant")
        self.assertEqual(
            serializer.data["history"][0]["thinking_log"],
            "Grouped expense rows before answering.",
        )
        self.assertEqual(serializer.data["history"][1]["type"], "output")
        self.assertEqual(
            serializer.data["history"][1]["output_json"]["document_info"]["filename"],
            "example.xlsx",
        )
        self.assertEqual(
            serializer.data["history"][1]["thinking_log"],
            "Normalized columns and preserved totals.",
        )

    def test_session_resume_serializer_supports_empty_history(self):
        session = self._session_stub()
        session.history = []

        serializer = SessionResumeSerializer(session)

        self.assertEqual(serializer.data["id"], "session-1")
        self.assertEqual(serializer.data["history"], [])

    def test_resume_history_item_serializer_rejects_unsupported_item_type(self):
        serializer = ResumeHistoryItemSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.to_representation(
                SimpleNamespace(
                    type="metadata",
                    id="meta-1",
                    created_at=datetime(2026, 4, 21, 10, 4, tzinfo=timezone.utc),
                )
            )

    def test_paginated_collection_serializer_defines_shared_pagination_fields(self):
        serializer = PaginatedCollectionSerializer(data={"count": 1, "limit": 10, "offset": 0})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["count"], 1)
        self.assertEqual(serializer.validated_data["limit"], 10)
        self.assertEqual(serializer.validated_data["offset"], 0)

    def test_paginated_chat_message_collection_serializer_reuses_base_fields(self):
        serializer = PaginatedChatMessageCollectionSerializer(
            data={"count": 1, "limit": 1, "offset": 0, "results": []}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["limit"], 1)

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
