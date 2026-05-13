import json
import uuid
from unittest.mock import MagicMock, patch
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

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        list(response.streaming_content)  # consume stream to trigger generator

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

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Lanjut", "session_id": str(session.id)},
            content_type="application/json",
        )
        list(response.streaming_content)  # consume to trigger DB persist

        self.assertEqual(Session.objects.filter(owner=self.user).count(), 1)

    @patch("llm.views._build_stream_event_generator")
    def test_edge_empty_generator_yields_no_first_event(self, mock_build_gen):
        def _empty():
            yield from ()

        mock_build_gen.return_value = _empty()

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.streaming_content), [])

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

    @patch("llm.views.generate_streaming_chat_response")
    def test_edge_generator_exit_is_handled_gracefully(self, mock_stream):
        from llm.views import _build_stream_event_generator

        mock_stream.return_value = iter(["chunk1", "chunk2"])
        mock_request = MagicMock()
        mock_request.is_aborted = lambda: False
        mock_request.user = self.user

        gen = _build_stream_event_generator(
            mock_request, None, [{"role": "user", "content": "hi"}], "hi"
        )
        next(gen)
        gen.close()

    @patch("llm.views.generate_streaming_chat_response")
    def test_edge_abort_stops_stream_without_persisting(self, mock_stream):
        from llm.views import _build_stream_event_generator

        def _chunks():
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"

        mock_stream.return_value = _chunks()
        call_count = {"n": 0}

        def _is_aborted():
            call_count["n"] += 1
            return call_count["n"] >= 2

        mock_request = MagicMock()
        mock_request.is_aborted = _is_aborted
        mock_request.user = self.user

        events = list(_build_stream_event_generator(
            mock_request, None, [{"role": "user", "content": "hi"}], "hi"
        ))

        self.assertFalse(Session.objects.filter(owner=self.user).exists())
        parsed = [
            json.loads(e[6:].strip())
            for e in events
            if e.startswith("data: ") and e.strip() != "data: [DONE]"
        ]
        done_events = [c for c in parsed if c.get("done")]
        self.assertEqual(len(done_events), 0)


class StreamSendMessageNegativeSessionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="stream-neg-session@example.com",
            name="Neg Session User",
            password="secret",
            status="verified",
        )
        self.client.force_authenticate(user=self.user)

    def test_negative_returns_404_when_session_id_not_found(self):
        fake_session_id = str(uuid.uuid4())

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi", "session_id": fake_session_id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    @patch("llm.views.logger")
    @patch("llm.views.generate_streaming_chat_response")
    def test_negative_service_error_sends_error_event(self, mock_stream, mock_logger):
        from llm.services.openai_client import OpenAIServiceError

        def _raise():
            yield "partial"
            raise OpenAIServiceError("provider error")

        mock_stream.return_value = _raise()

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        events = _collect_sse(response)
        error_event = next((e for e in events if "error" in e), None)

        self.assertIsNotNone(error_event)
        self.assertFalse(Session.objects.filter(owner=self.user).exists())

    @patch("llm.views.logger")
    @patch("llm.views.generate_streaming_chat_response")
    def test_negative_unexpected_exception_sends_error_event_and_logs(
        self, mock_stream, mock_logger
    ):
        def _raise():
            yield "partial"
            raise RuntimeError("unexpected boom")

        mock_stream.return_value = _raise()

        response = self.client.post(
            "/llm/send-message/stream/",
            {"message": "Hi"},
            content_type="application/json",
        )
        events = _collect_sse(response)
        error_event = next((e for e in events if "error" in e), None)

        self.assertIsNotNone(error_event)
        mock_logger.exception.assert_called_once_with(
            "Unexpected error during streaming send_message."
        )
