from django.test import SimpleTestCase, override_settings
from unittest.mock import Mock, patch

from llm.services.openai_client import OpenAIServiceError, generate_json, generate_text


class OpenAIClientServiceTest(SimpleTestCase):
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

        with self.assertRaises(OpenAIServiceError):
            generate_json({"source": "upload"})

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_raises_for_json_primitive_output(self, mock_generate_text):
        mock_generate_text.return_value = '"ok"'

        with self.assertRaises(OpenAIServiceError):
            generate_json({"source": "upload"})

