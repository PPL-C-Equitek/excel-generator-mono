import json

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from unittest.mock import Mock, patch

from llm.services.openai_client import OpenAIServiceError, OpenAIUpstreamError, generate_json, generate_text


class DummyAuthenticationError(Exception):
    pass


class DummyRateLimitError(Exception):
    pass


class DummyTimeoutError(Exception):
    pass


class DummyAPIStatusError(Exception):
    def __init__(self, message="API status failure", status_code=None):
        super().__init__(message)
        self.status_code = status_code


class DummyAPIError(Exception):
    pass


class DummyAPIConnectionError(Exception):
    pass


class OpenAIClientServiceTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_uses_default_model(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        result = generate_text("Say hi")

        self.assertEqual(result, "ok result")
        mock_openai.assert_called_once_with(api_key="test-key")
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="Say hi",
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="Return strict JSON only.",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_passes_system_prompt_as_instructions(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text='{"status":"ok"}')

        result = generate_text('{"input":"data"}')

        self.assertEqual(result, '{"status":"ok"}')
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input='{"input":"data"}',
            instructions="Return strict JSON only.",
        )

    @override_settings(OPENAI_API_KEY="", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_raises_when_key_missing(self, mock_openai):
        with self.assertRaises(OpenAIServiceError):
            generate_text("Hello")
        mock_openai.assert_not_called()

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_raises_when_output_missing(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="")

        with self.assertRaises(OpenAIServiceError):
            generate_text("Hello")

    def test_generate_text_raises_for_empty_prompt(self):
        with self.assertRaises(ValueError):
            generate_text("")

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.AuthenticationError", new=DummyAuthenticationError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_authentication_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAuthenticationError("bad auth")

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 401)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.RateLimitError", new=DummyRateLimitError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_rate_limit_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyRateLimitError("rate limit")

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 429)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APITimeoutError", new=DummyTimeoutError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_timeout_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyTimeoutError("timeout")

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 504)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_status_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError("api status", status_code=418)

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIError", new=DummyAPIError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIError("api failure")

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIConnectionError", new=DummyAPIConnectionError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_connection_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIConnectionError("connection aborted")

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 502)

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_parses_object_response(self, mock_generate_text):
        mock_generate_text.return_value = '{"status":"ok","rows":[1,2]}'

        result = generate_json({"source": "upload"})

        self.assertEqual(result, {"status": "ok", "rows": [1, 2]})
        mock_generate_text.assert_called_once_with(prompt='{"source": "upload"}')

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_parses_array_response(self, mock_generate_text):
        mock_generate_text.return_value = '[{"a":1}]'

        result = generate_json([{"input": 1}])

        self.assertEqual(result, [{"a": 1}])
        mock_generate_text.assert_called_once_with(prompt='[{"input": 1}]')

    def test_generate_json_rejects_non_json_object_or_array_input(self):
        with self.assertRaises(ValueError):
            generate_json("plain text")

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_raises_for_invalid_json_output(self, mock_generate_text):
        mock_generate_text.return_value = "not valid json"

        with self.assertRaises(OpenAIServiceError) as exc_ctx:
            generate_json({"source": "upload"})
        self.assertIsInstance(exc_ctx.exception.__cause__, json.JSONDecodeError)

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_raises_for_json_primitive_output(self, mock_generate_text):
        mock_generate_text.return_value = '"ok"'

        with self.assertRaises(OpenAIServiceError):
            generate_json({"source": "upload"})

    @override_settings(
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="",
        LLM_CACHE_TTL_SECONDS=300,
    )
    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_caches_identical_input(self, mock_generate_text):
        mock_generate_text.return_value = '{"status":"ok"}'

        first_result = generate_json({"source": "upload"})
        second_result = generate_json({"source": "upload"})

        self.assertEqual(first_result, {"status": "ok"})
        self.assertEqual(second_result, {"status": "ok"})
        mock_generate_text.assert_called_once_with(prompt='{"source": "upload"}')

    @override_settings(
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="",
        LLM_CACHE_TTL_SECONDS=300,
    )
    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_cache_key_is_order_independent_for_objects(self, mock_generate_text):
        mock_generate_text.return_value = '{"status":"ok"}'

        first_result = generate_json({"b": 2, "a": 1})
        second_result = generate_json({"a": 1, "b": 2})

        self.assertEqual(first_result, {"status": "ok"})
        self.assertEqual(second_result, {"status": "ok"})
        self.assertEqual(mock_generate_text.call_count, 1)

    @override_settings(OPENAI_MODEL="gpt-4.1-mini", OPENAI_SYSTEM_PROMPT="", LLM_CACHE_TTL_SECONDS=300)
    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_cache_key_includes_model_and_system_prompt(self, mock_generate_text):
        mock_generate_text.side_effect = ['{"source":"model-1"}', '{"source":"model-2"}']

        with override_settings(OPENAI_MODEL="gpt-4.1-mini", OPENAI_SYSTEM_PROMPT="prompt-a"):
            first_result = generate_json({"source": "upload"})

        with override_settings(OPENAI_MODEL="gpt-4.1", OPENAI_SYSTEM_PROMPT="prompt-b"):
            second_result = generate_json({"source": "upload"})

        self.assertEqual(first_result, {"source": "model-1"})
        self.assertEqual(second_result, {"source": "model-2"})
        self.assertEqual(mock_generate_text.call_count, 2)

    @override_settings(
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="",
        LLM_CACHE_TTL_SECONDS=0,
    )
    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_does_not_cache_when_ttl_is_zero(self, mock_generate_text):
        mock_generate_text.return_value = '{"status":"ok"}'

        first_result = generate_json({"source": "upload"})
        second_result = generate_json({"source": "upload"})

        self.assertEqual(first_result, {"status": "ok"})
        self.assertEqual(second_result, {"status": "ok"})
        self.assertEqual(mock_generate_text.call_count, 2)

