import json
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from unittest.mock import Mock, patch

from llm.services.generation_service import (
    CustomSchemaNotFoundError,
    DjangoCustomSchemaPromptSource,
    JsonGenerationService,
    LlmGenerationService,
    compose_system_prompt,
)
from llm.services.openai_client import (
    OpenAIServiceError,
    OpenAIUpstreamError,
    generate_chat_response,
    generate_json,
    generate_text,
)


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

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="Base instructions",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_prefers_explicit_system_prompt_override(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text='{"status":"ok"}')

        result = generate_text('{"input":"data"}', system_prompt="Schema-specific prompt")

        self.assertEqual(result, '{"status":"ok"}')
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input='{"input":"data"}',
            instructions="Schema-specific prompt",
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT=None,
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_omits_instructions_when_setting_is_not_string(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text='{"status":"ok"}')

        result = generate_text('{"input":"data"}')

        self.assertEqual(result, '{"status":"ok"}')
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input='{"input":"data"}',
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
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_status_401_to_401(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError("api status", status_code=401)

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 401)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_status_429_to_429(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError("api status", status_code=429)

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 429)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_maps_api_status_504_to_504(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError("api status", status_code=504)

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 504)

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
        mock_generate_text.assert_called_once_with(
            prompt='{"source": "upload"}',
            system_prompt=None,
        )

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_passes_system_prompt_override(self, mock_generate_text):
        mock_generate_text.return_value = '{"status":"ok","rows":[1,2]}'
        result = generate_json(
            {"source": "upload"},
            system_prompt="Schema-specific prompt",
        )

        self.assertEqual(result, {"status": "ok", "rows": [1, 2]})
        mock_generate_text.assert_called_once_with(
            prompt='{"source": "upload"}',
            system_prompt="Schema-specific prompt",
        )

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_parses_array_response(self, mock_generate_text):
        mock_generate_text.return_value = '[{"a":1}]'

        result = generate_json([{"input": 1}])

        self.assertEqual(result, [{"a": 1}])
        mock_generate_text.assert_called_once_with(
            prompt='[{"input": 1}]',
            system_prompt=None,
        )

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

    @patch("llm.services.openai_client.generate_text")
    def test_generate_json_does_not_cache_identical_input(self, mock_generate_text):
        mock_generate_text.side_effect = ['{"status":"first"}', '{"status":"second"}']

        first_result = generate_json({"source": "upload"})
        second_result = generate_json({"source": "upload"})

        self.assertEqual(first_result, {"status": "first"})
        self.assertEqual(second_result, {"status": "second"})
        self.assertEqual(mock_generate_text.call_count, 2)


class LlmGenerationServiceTest(SimpleTestCase):
    @override_settings(OPENAI_SYSTEM_PROMPT="  Base instructions  ")
    def test_get_base_system_prompt_strips_setting_value(self):
        from llm.services.generation_service import get_base_system_prompt

        result = get_base_system_prompt()

        self.assertEqual(result, "Base instructions")

    @override_settings(OPENAI_SYSTEM_PROMPT=None)
    def test_get_base_system_prompt_returns_empty_string_for_non_string_setting(self):
        from llm.services.generation_service import get_base_system_prompt

        result = get_base_system_prompt()

        self.assertEqual(result, "")

    def test_compose_system_prompt_combines_base_and_schema_fragment(self):
        result = compose_system_prompt(
            "Base prompt.",
            "Use only invoice_number and total_amount.",
        )

        self.assertEqual(
            result,
            "Base prompt.\n\nUse only invoice_number and total_amount.",
        )

    def test_compose_system_prompt_returns_none_for_blank_inputs(self):
        result = compose_system_prompt("   ", "   ")

        self.assertIsNone(result)

    def test_json_generation_service_uses_injected_text_provider(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        result = service.generate({"source": "upload"})

        self.assertEqual(result, {"status": "ok"})
        text_provider.generate_text.assert_called_once_with(
            prompt='{"source": "upload"}'
        )

    def test_json_generation_service_passes_system_prompt_to_injected_provider(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        result = service.generate(
            {"source": "upload"},
            system_prompt="Schema-specific prompt",
        )

        self.assertEqual(result, {"status": "ok"})
        text_provider.generate_text.assert_called_once_with(
            prompt='{"source": "upload"}',
            system_prompt="Schema-specific prompt",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_uses_base_prompt_when_no_schema_selected(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.return_value = {"status": "ok"}
        schema_prompt_source = Mock()
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "Base prompt.",
        )

        result = service.generate({"sheet": "Sheet1"})

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint=None,
        )
        schema_prompt_source.get_prompt_fragment.assert_not_called()
        json_generator.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            system_prompt="Base prompt.\n\nExtraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_combines_base_and_schema_prompts(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.return_value = {"status": "ok"}
        schema_prompt_source = Mock()
        schema_prompt_source.get_prompt_fragment.return_value = (
            "Use only invoice_number and total_amount."
        )
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "Base prompt.",
        )

        result = service.generate({"sheet": "Sheet1"}, custom_schema_id="schema-1")

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint="Use only invoice_number and total_amount.",
        )
        schema_prompt_source.get_prompt_fragment.assert_called_once_with("schema-1")
        json_generator.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            system_prompt="Base prompt.\n\nExtraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_passes_none_when_no_prompt_exists(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.return_value = {"status": "ok"}
        schema_prompt_source = Mock()
        schema_prompt_source.get_prompt_fragment.return_value = "   "
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "   ",
        )

        result = service.generate({"sheet": "Sheet1"}, custom_schema_id="schema-1")

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint="   ",
        )
        json_generator.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            system_prompt="Extraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_uses_extraction_prompt_from_input_json(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.return_value = {"status": "ok"}
        schema_prompt_source = Mock()
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "",
        )

        result = service.generate({"name": "Pen", "price": 5000})

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint=None,
        )
        json_generator.generate.assert_called_once_with(
            input_json={"name": "Pen", "price": 5000},
            system_prompt="Extraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_appends_custom_schema_to_extraction_prompt(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.return_value = {"status": "ok"}
        schema_prompt_source = Mock()
        schema_prompt_source.get_prompt_fragment.return_value = (
            "Use only invoice_number and total_amount."
        )
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "",
        )

        result = service.generate(
            {"name": "Pen", "price": 5000},
            custom_schema_id="schema-1",
        )

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint="Use only invoice_number and total_amount.",
        )
        schema_prompt_source.get_prompt_fragment.assert_called_once_with("schema-1")
        json_generator.generate.assert_called_once_with(
            input_json={"name": "Pen", "price": 5000},
            system_prompt="Extraction prompt.",
        )

    @patch("llm.services.generation_service.CustomSchema.objects.get")
    def test_django_custom_schema_prompt_source_returns_schema_prompt_fragment(
        self, mock_get
    ):
        owner_id = "owner-1"
        mock_get.return_value = SimpleNamespace(prompt_fragment="Schema prompt.")
        prompt_source = DjangoCustomSchemaPromptSource(owner_id=owner_id)

        result = prompt_source.get_prompt_fragment("schema-1")

        self.assertEqual(result, "Schema prompt.")
        mock_get.assert_called_once_with(pk="schema-1", owner_id=owner_id)

    @patch("llm.services.generation_service.CustomSchema.objects.get")
    def test_django_custom_schema_prompt_source_raises_custom_not_found_error(
        self, mock_get
    ):
        from custom_schemas.models import CustomSchema

        mock_get.side_effect = CustomSchema.DoesNotExist
        prompt_source = DjangoCustomSchemaPromptSource(owner_id="owner-1")

        with self.assertRaises(CustomSchemaNotFoundError):
            prompt_source.get_prompt_fragment("missing-schema")

    @patch("llm.services.generation_service.CustomSchema.objects.get")
    def test_django_custom_schema_prompt_source_rejects_anonymous_access(
        self, mock_get
    ):
        prompt_source = DjangoCustomSchemaPromptSource(owner_id=None)

        with self.assertRaises(CustomSchemaNotFoundError):
            prompt_source.get_prompt_fragment("schema-1")

        mock_get.assert_not_called()


class GenerateChatResponseServiceTest(SimpleTestCase):
    # Positive

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_returns_reply_from_first_choice(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Halo!"))]
        )

        result = generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(result, "Halo!")

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_calls_chat_completions_with_correct_payload(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="ok"))]
        )
        messages = [{"role": "user", "content": "Halo"}]

        generate_chat_response(messages)

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            messages=messages,
        )

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_passes_full_history_to_api(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Follow-up reply"))]
        )
        messages = [
            {"role": "user", "content": "Pesan pertama"},
            {"role": "assistant", "content": "Balasan pertama"},
            {"role": "user", "content": "Pesan lanjutan"},
        ]

        result = generate_chat_response(messages)

        self.assertEqual(result, "Follow-up reply")
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            messages=messages,
        )

    # Negative

    def test_generate_chat_response_raises_for_empty_messages(self):
        with self.assertRaises(ValueError):
            generate_chat_response([])

    @override_settings(OPENAI_API_KEY="", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_raises_when_api_key_missing(self, mock_openai):
        with self.assertRaises(OpenAIServiceError):
            generate_chat_response([{"role": "user", "content": "Halo"}])

        mock_openai.assert_not_called()

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_raises_when_reply_content_is_empty(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=""))]
        )

        with self.assertRaises(OpenAIServiceError):
            generate_chat_response([{"role": "user", "content": "Halo"}])

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.AuthenticationError", new=DummyAuthenticationError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_maps_authentication_error_to_401(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyAuthenticationError("bad auth")

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 401)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.RateLimitError", new=DummyRateLimitError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_maps_rate_limit_error_to_429(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyRateLimitError("rate limit")

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 429)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APITimeoutError", new=DummyTimeoutError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_maps_timeout_error_to_504(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyTimeoutError("timeout")

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 504)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIConnectionError", new=DummyAPIConnectionError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_maps_connection_error_to_502(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyAPIConnectionError("conn aborted")

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_maps_api_status_error(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyAPIStatusError("api status", status_code=502)

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 502)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_raises_when_choices_missing_or_invalid(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Simulating IndexError by returning empty choices
        mock_client.chat.completions.create.return_value = Mock(choices=[])

        with self.assertRaises(OpenAIServiceError):
            generate_chat_response([{"role": "user", "content": "Halo"}])
            
        # Simulating AttributeError by returning an object without choices
        mock_client.chat.completions.create.return_value = Mock(spec=[])
        
        with self.assertRaises(OpenAIServiceError):
            generate_chat_response([{"role": "user", "content": "Halo"}])
