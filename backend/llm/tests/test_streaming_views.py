import json
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from authentication.models import User
from chat_sessions.models import Session


def _collect_sse(streaming_response):
    """Parse SSE response body into a list of event data dicts."""
    events = []
    for line in streaming_response.streaming_content:
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("data: ") and line.strip() != "data: [DONE]":
            events.append(json.loads(line[6:].strip()))
    return events


class StreamSendMessagePositiveTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="stream@example.com",
            name="Stream User",
            password="secret",
            status="verified",
        )
        self.client.force_authenticate(user=self.user)

    @patch("llm.views.generate_streaming_chat_response")
    def test_positive_response_content_type_is_text_event_stream(self, mock_stream):
        mock_stream.return_value = iter(["Halo"])

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])

    @patch("llm.views.generate_streaming_chat_response")
    def test_positive_streams_chunks_as_sse_data_lines(self, mock_stream):
        mock_stream.return_value = iter(["Halo ", "dunia"])

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        events = _collect_sse(response)
        chunks = [e["chunk"] for e in events if "chunk" in e]

        self.assertEqual(chunks, ["Halo ", "dunia"])

    @patch("llm.views.generate_streaming_chat_response")
    def test_positive_session_and_messages_persisted_after_stream_completes(self, mock_stream):
        mock_stream.return_value = iter(["Oke"])

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hitung total"},
            content_type="application/json",
        )
        list(response.streaming_content)  # consume stream to trigger DB persist

        session = Session.objects.filter(owner=self.user).first()
        self.assertIsNotNone(session)
        roles = list(session.messages.values_list("role", flat=True))
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    @patch("llm.views.generate_streaming_chat_response")
    def test_positive_final_event_contains_session_id(self, mock_stream):
        mock_stream.return_value = iter(["Ok"])

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        events = _collect_sse(response)
        done_event = next((e for e in events if "session_id" in e), None)

        self.assertIsNotNone(done_event)
        self.assertTrue(done_event.get("done"))


class StreamSendMessageNegativeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="stream-neg@example.com",
            name="Neg User",
            password="secret",
            status="verified",
        )
        self.client.force_authenticate(user=self.user)

    def test_negative_returns_415_for_non_json_content_type(self):
        response = self.client.post(
            "/llm/send-message/stream/",
            "message=Hi",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 415)

    def test_negative_returns_400_when_message_missing(self):
        response = self.client.post(
            "/llm/send-message/stream/",
            {},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_negative_returns_401_when_unauthenticated(self):
        client = APIClient()
        response = client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("llm.views.generate_streaming_chat_response")
    def test_negative_error_chunk_sent_on_provider_timeout(self, mock_stream):
        from llm.services.openai_client import OpenAIUpstreamError

        def _raise_mid_stream():
            yield "Sebentar"
            raise OpenAIUpstreamError("timeout", status_code=504)

        mock_stream.return_value = _raise_mid_stream()

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        events = _collect_sse(response)
        error_event = next((e for e in events if "error" in e), None)

        self.assertIsNotNone(error_event)

    @patch("llm.views.generate_streaming_chat_response")
    def test_negative_no_db_persist_when_provider_errors_mid_stream(self, mock_stream):
        from llm.services.openai_client import OpenAIUpstreamError

        def _raise():
            yield from []
            raise OpenAIUpstreamError("fail", status_code=502)

        mock_stream.return_value = _raise()

        self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )

        self.assertFalse(Session.objects.filter(owner=self.user).exists())


class StreamSendMessageEdgeCaseTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="stream-edge@example.com",
            name="Edge User",
            password="secret",
            status="verified",
        )
        self.client.force_authenticate(user=self.user)

    @patch("llm.views.generate_streaming_chat_response")
    def test_edge_existing_session_id_continues_session(self, mock_stream):
        mock_stream.return_value = iter(["Reply"])
        session = Session.objects.create(owner=self.user, title="Existing")

        self.client.post(
            "/llm/send-message/stream/",
            {"message": "Lanjut", "session_id": str(session.id)},
            content_type="application/json",
        )

        self.assertEqual(Session.objects.filter(owner=self.user).count(), 1)

    @patch("llm.views.generate_streaming_chat_response")
    def test_edge_returns_503_on_config_error(self, mock_stream):
        from llm.services.openai_client import OpenAIConfigurationError

        def _raise():
            yield from []
            raise OpenAIConfigurationError("no key")

        mock_stream.return_value = _raise()

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
