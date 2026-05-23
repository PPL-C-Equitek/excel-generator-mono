from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from llm.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIUpstreamError,
    generate_streaming_chat_response,
    reset_chat_completion_client_cache,
)


class GenerateStreamingChatResponseTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        reset_chat_completion_client_cache()

    def _make_stream(self, chunks):
        mock_stream = MagicMock()
        mock_chunks = []
        for text in chunks:
            chunk = MagicMock()
            chunk.choices[0].delta.content = text
            mock_chunks.append(chunk)
        mock_stream.__iter__ = MagicMock(return_value=iter(mock_chunks))
        mock_stream.close = MagicMock()
        return mock_stream

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_positive_yields_chunks_from_openai_stream(self, mock_build_client):
        mock_stream = self._make_stream(["Halo ", "dunia"])
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        result = list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(result, ["Halo ", "dunia"])

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_edge_empty_delta_chunks_are_skipped(self, mock_build_client):
        mock_stream = self._make_stream(["Halo", None, "", "!"])
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        result = list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(result, ["Halo", "!"])

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_timeout(self, mock_build_client):
        from openai import APITimeoutError
        mock_build_client.return_value.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock()
        )

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 504)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_timeout_mid_stream(self, mock_build_client):
        from openai import APITimeoutError

        def _stream_then_timeout():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="partial"))])
            raise APITimeoutError(request=MagicMock())

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=_stream_then_timeout())
        mock_stream.close = MagicMock()
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 504)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_auth_error_mid_stream(self, mock_build_client):
        from openai import AuthenticationError

        def _stream_then_auth_error():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="partial"))])
            raise AuthenticationError(message="bad key", response=MagicMock(), body={})

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=_stream_then_auth_error())
        mock_stream.close = MagicMock()
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_rate_limit_mid_stream(self, mock_build_client):
        from openai import RateLimitError

        def _stream_then_rate_limit():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="partial"))])
            raise RateLimitError(message="rate limit", response=MagicMock(), body={})

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=_stream_then_rate_limit())
        mock_stream.close = MagicMock()
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 429)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_api_status_mid_stream(self, mock_build_client):
        from openai import APIStatusError

        def _stream_then_status_error():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="partial"))])
            raise APIStatusError(message="bad status", response=MagicMock(status_code=503), body={})

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=_stream_then_status_error())
        mock_stream.close = MagicMock()
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4")
    @patch("llm.services.openai_client._build_client")
    def test_negative_raises_upstream_error_on_connection_error_mid_stream(self, mock_build_client):
        from openai import APIConnectionError

        def _stream_then_connection_error():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="partial"))])
            raise APIConnectionError(request=MagicMock())

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=_stream_then_connection_error())
        mock_stream.close = MagicMock()
        mock_build_client.return_value.chat.completions.create.return_value = mock_stream

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="")
    def test_negative_raises_config_error_when_api_key_missing(self):
        with self.assertRaises(OpenAIConfigurationError):
            list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))
