import json
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from unittest.mock import Mock, patch

from llm.services import openai_client
from llm.services.generation_service import (
    _apply_extracted_payload_budget,
    _apply_prompt_payload_budget,
    _build_prompt_budget_summary,
    _compact_input_json_for_prompt,
    _extract_ocr_context,
    _normalize_user_prompt,
    _resolve_positive_int_setting as _resolve_generation_positive_int_setting,
    _truncate_table_rows,
    _truncate_text_cell,
    CustomSchemaNotFoundError,
    DjangoCustomSchemaPromptSource,
    JsonGenerationService,
    LlmGenerationService,
    compose_system_prompt,
)
from llm.services.openai_client import (
    OpenAITextGenerationProvider,
    OpenAIServiceError,
    OpenAIUpstreamError,
    _apply_generation_options,
    _build_chat_generation_options,
    _build_client,
    _build_client_from_signature,
    _build_prompt_context_from_messages,
    _build_response_generation_options,
    _extract_message_content_for_budget,
    _get_chat_completion_client,
    _map_api_status_to_http,
    _normalize_chat_message_content,
    _resolve_adaptive_max_output_tokens,
    _resolve_common_generation_options,
    _resolve_openai_max_retries,
    _resolve_openai_timeout_seconds,
    _resolve_optional_openai_max_output_tokens,
    _resolve_optional_openai_seed,
    _resolve_optional_openai_temperature,
    _resolve_positive_float_setting,
    _resolve_positive_int_setting as _resolve_openai_positive_int_setting,
    reset_chat_completion_client_cache,
    reset_text_generation_provider_cache,
    generate_chat_response,
    generate_json,
    generate_streaming_chat_response,
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


class CompactInputJsonForPromptTest(SimpleTestCase):
    @override_settings(
        LLM_PROMPT_MAX_TABLES=True,
        LLM_PROMPT_MAX_ROWS_PER_TABLE=-2,
        LLM_PROMPT_MAX_COLUMNS_PER_ROW=2.9,
        LLM_PROMPT_MAX_CELL_CHARS="4",
    )
    def test_generation_positive_int_setting_partitions(self):
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_TABLES", 7), 7)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_ROWS_PER_TABLE", 7), 7)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_COLUMNS_PER_ROW", 7), 2)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_CELL_CHARS", 7), 4)

    @override_settings(
        LLM_PROMPT_MAX_TABLES="",
        LLM_PROMPT_MAX_ROWS_PER_TABLE="bad",
        LLM_PROMPT_MAX_COLUMNS_PER_ROW="0",
        LLM_PROMPT_MAX_CELL_CHARS=object(),
    )
    def test_generation_positive_int_setting_invalid_partitions(self):
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_TABLES", 7), 7)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_ROWS_PER_TABLE", 7), 7)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_COLUMNS_PER_ROW", 7), 7)
        self.assertEqual(_resolve_generation_positive_int_setting("LLM_PROMPT_MAX_CELL_CHARS", 7), 7)

    def test_prompt_budget_cell_and_row_partitions(self):
        self.assertEqual(_truncate_text_cell(12, max_chars=3), 12)
        self.assertEqual(_truncate_text_cell("  ok  ", max_chars=3), "ok")
        self.assertEqual(_truncate_text_cell("abcdef", max_chars=3), "abc...")
        self.assertEqual(_truncate_table_rows("raw", 1, 1, 3), "raw")
        self.assertEqual(
            _truncate_table_rows(
                [
                    ["abcdef", "second"],
                    {"a": "abcdef", "b": "second"},
                    {"a": "ok"},
                    "abcdef",
                ],
                max_rows=4,
                max_columns=1,
                max_cell_chars=3,
            ),
            [["abc..."], {"a": "abc..."}, {"a": "ok"}, "abc..."],
        )

    def test_extracted_payload_budget_partitions(self):
        self.assertEqual(_apply_extracted_payload_budget("raw", 1, 1, 1, 3), "raw")
        self.assertEqual(
            _apply_extracted_payload_budget(
                {
                    "Sheet1": [["abcdef", "second"]],
                    "Sheet2": [["kept"]],
                },
                max_tables=2,
                max_rows=1,
                max_columns=1,
                max_cell_chars=3,
            ),
            {"Sheet1": [["abc..."]], "Sheet2": [["kep..."]]},
        )

    def test_prompt_budget_summary_partitions(self):
        self.assertEqual(
            _build_prompt_budget_summary([{"row": 1}, {"row": 2}]),
            {"_prompt_budget": {"applied": True, "mode": "summary", "list_items": 2}},
        )
        self.assertEqual(
            _build_prompt_budget_summary(
                {
                    "filename": " report.pdf ",
                    "format": " pdf ",
                    "user_prompt": " " + ("x" * 400),
                    "extracted": {"Sheet1": [], "Sheet2": []},
                }
            ),
            {
                "_prompt_budget": {"applied": True, "mode": "summary"},
                "filename": "report.pdf",
                "format": "pdf",
                "user_prompt": "x" * 300,
                "extracted_summary": {
                    "table_count": 2,
                    "table_names": ["Sheet1", "Sheet2"],
                },
            },
        )

    @override_settings(LLM_PROMPT_MAX_CHARS=80)
    def test_apply_prompt_payload_budget_handles_list_summary(self):
        result = _apply_prompt_payload_budget([{"value": "x" * 200}])

        self.assertEqual(
            result,
            {"_prompt_budget": {"applied": True, "mode": "summary", "list_items": 1}},
        )

    @override_settings(LLM_PROMPT_MAX_CHARS=1)
    def test_apply_prompt_payload_budget_returns_summary_without_user_prompt(self):
        result = _apply_prompt_payload_budget([{"value": "x" * 200}])

        self.assertEqual(
            result,
            {"_prompt_budget": {"applied": True, "mode": "summary", "list_items": 1}},
        )

    @override_settings(
        LLM_PROMPT_MAX_CHARS=120,
        LLM_PROMPT_MAX_TABLES=1,
        LLM_PROMPT_MAX_ROWS_PER_TABLE=1,
        LLM_PROMPT_MAX_COLUMNS_PER_ROW=1,
        LLM_PROMPT_MAX_CELL_CHARS=4,
    )
    def test_apply_prompt_payload_budget_compacts_nested_original_input(self):
        result = _apply_prompt_payload_budget(
            {
                "original_input_json": {
                    "filename": "nested.pdf",
                    "extracted": {"Sheet1": [["abcdef", "ignored"]]},
                    "user_prompt": "keep rows",
                },
                "previous_output_json": {"content_data": []},
                "validation_log": {"errors": []},
                "extra": "x" * 200,
            }
        )

        self.assertIn("_prompt_budget", result)
        self.assertEqual(result["_prompt_budget"]["mode"], "summary")

    @override_settings(LLM_PROMPT_MAX_CHARS=70)
    def test_apply_prompt_payload_budget_trims_summary_user_prompt_when_needed(self):
        result = _apply_prompt_payload_budget(
            {
                "filename": "report.pdf",
                "user_prompt": "x" * 400,
                "extracted": {"Sheet1": [["value"]]},
            }
        )

        self.assertEqual(result["_prompt_budget"]["mode"], "summary")
        self.assertLessEqual(len(result["user_prompt"]), 11)

    def test_normalize_user_prompt_partitions(self):
        payload = {"user_prompt": 12}
        _normalize_user_prompt(payload)
        self.assertEqual(payload, {"user_prompt": 12})

        payload = {"user_prompt": "  keep rows  "}
        _normalize_user_prompt(payload)
        self.assertEqual(payload, {"user_prompt": "keep rows"})

        payload = {"user_prompt": "   "}
        _normalize_user_prompt(payload)
        self.assertEqual(payload, {})

    def test_compact_input_json_for_prompt_isp_partitions(self):
        scenarios = (
            {
                "name": "non_dict_payload_is_passthrough",
                "input_json": [{"sheet": "Sheet1"}],
                "expected": [{"sheet": "Sheet1"}],
            },
            {
                "name": "dict_without_extracted_is_passthrough",
                "input_json": {"filename": "report.pdf", "format": "pdf"},
                "expected": {"filename": "report.pdf", "format": "pdf"},
            },
            {
                "name": "dict_with_extracted_drops_upload_wrapper_noise",
                "input_json": {
                    "status": "success",
                    "message": "uploaded",
                    "size": 100,
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                },
                "expected": {
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                },
            },
            {
                "name": "trimmed_user_prompt_is_preserved",
                "input_json": {
                    "status": "success",
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                    "user_prompt": "  Only paid rows  ",
                },
                "expected": {
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                    "user_prompt": "Only paid rows",
                },
            },
            {
                "name": "blank_user_prompt_is_removed",
                "input_json": {
                    "status": "success",
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                    "user_prompt": "   ",
                },
                "expected": {
                    "filename": "report.pdf",
                    "extracted": {"Sheet1": [["a"], ["1"]]},
                },
            },
        )

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                result = _compact_input_json_for_prompt(scenario["input_json"])
                self.assertEqual(result, scenario["expected"])

    def test_compact_input_json_for_prompt_compacts_nested_refinement_original_input(self):
        input_json = {
            "original_input_json": {
                "status": "success",
                "message": "uploaded",
                "size": 100,
                "filename": "report.pdf",
                "extracted": {"Sheet1": [["a"], ["1"]]},
                "user_prompt": "  Keep only paid rows  ",
            },
            "previous_output_json": {"content_data": []},
            "validation_log": {"iteration": 1, "verdict": "invalid"},
        }

        result = _compact_input_json_for_prompt(input_json)

        self.assertEqual(
            result["original_input_json"],
            {
                "filename": "report.pdf",
                "extracted": {"Sheet1": [["a"], ["1"]]},
                "user_prompt": "Keep only paid rows",
            },
        )
        self.assertEqual(result["previous_output_json"], {"content_data": []})
        self.assertEqual(result["validation_log"], {"iteration": 1, "verdict": "invalid"})

    def test_compact_input_json_for_prompt_handles_refinement_wrapper_with_list_original_input(self):
        input_json = {
            "original_input_json": [
                {"table_name": "Sheet1", "rows": [{"id": 1}]},
            ],
            "previous_output_json": {"content_data": []},
            "validation_log": {"iteration": 1, "verdict": "invalid"},
        }

        result = _compact_input_json_for_prompt(input_json)

        self.assertEqual(result["original_input_json"], input_json["original_input_json"])
        self.assertEqual(result["previous_output_json"], {"content_data": []})
        self.assertEqual(result["validation_log"], {"iteration": 1, "verdict": "invalid"})

    def test_compact_input_json_for_prompt_keeps_wrapper_when_original_input_not_dict_or_list(self):
        input_json = {
            "original_input_json": "raw-content",
            "previous_output_json": {"content_data": []},
            "validation_log": {"iteration": 1, "verdict": "invalid"},
        }

        result = _compact_input_json_for_prompt(input_json)

        self.assertEqual(result, input_json)

    def test_compact_input_json_for_prompt_does_not_mutate_original_payload(self):
        input_json = {
            "status": "success",
            "message": "uploaded",
            "size": 100,
            "filename": "report.pdf",
            "extracted": {"Sheet1": [["a"], ["1"]]},
            "user_prompt": "  Keep only paid rows  ",
        }
        expected_original = {
            "status": "success",
            "message": "uploaded",
            "size": 100,
            "filename": "report.pdf",
            "extracted": {"Sheet1": [["a"], ["1"]]},
            "user_prompt": "  Keep only paid rows  ",
        }

        result = _compact_input_json_for_prompt(input_json)

        self.assertEqual(
            result,
            {
                "filename": "report.pdf",
                "extracted": {"Sheet1": [["a"], ["1"]]},
                "user_prompt": "Keep only paid rows",
            },
        )
        self.assertEqual(input_json, expected_original)

    def test_extract_ocr_context_finds_nested_metadata_variants(self):
        scenarios = (
            ({"ocr_metadata": {"confidence_score": 91.0}}, 91.0),
            ({"original_input_json": {"ocr_metadata": {"confidence_score": 82.0}}}, 82.0),
            ({"input_json": {"ocr_metadata": {"confidence_score": 73.0}}}, 73.0),
            ({"payload": {"ocr_metadata": {"confidence_score": 64.0}}}, 64.0),
            ({"extracted": {"ocr_metadata": {"confidence_score": 55.0}}}, 55.0),
        )

        for payload, expected_confidence in scenarios:
            with self.subTest(payload=payload):
                context = _extract_ocr_context(payload)
                self.assertEqual(context["confidence_score"], expected_confidence)

    def test_extract_ocr_context_returns_none_for_list_and_empty_nested_payloads(self):
        self.assertIsNone(_extract_ocr_context([{"ocr_metadata": {"confidence_score": 1.0}}]))
        self.assertIsNone(
            _extract_ocr_context(
                {
                    "original_input_json": {},
                    "input_json": [],
                    "payload": None,
                    "extracted": {},
                }
            )
        )


class OpenAIClientServiceTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        reset_text_generation_provider_cache()

    def tearDown(self):
        reset_text_generation_provider_cache()
        super().tearDown()

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
        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
        )
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="Say hi",
        )

    @override_settings(
        OPENAI_TIMEOUT_SECONDS=True,
        OPENAI_MAX_RETRIES=True,
        OPENAI_TEMPERATURE=True,
        OPENAI_SEED=True,
        OPENAI_MAX_OUTPUT_TOKENS=True,
    )
    def test_openai_option_resolvers_ignore_boolean_values(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertIsNone(_resolve_optional_openai_seed())
        self.assertIsNone(_resolve_optional_openai_max_output_tokens())

    @override_settings(
        OPENAI_TIMEOUT_SECONDS=-1,
        OPENAI_MAX_RETRIES=-1,
        OPENAI_TEMPERATURE=3,
        OPENAI_SEED=2.9,
        OPENAI_MAX_OUTPUT_TOKENS=12.8,
    )
    def test_openai_option_resolvers_handle_numeric_boundaries(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertEqual(_resolve_optional_openai_seed(), 2)
        self.assertEqual(_resolve_optional_openai_max_output_tokens(), 12)

    @override_settings(
        OPENAI_TIMEOUT_SECONDS="7.25",
        OPENAI_MAX_RETRIES=3.9,
        OPENAI_TEMPERATURE="1.5",
        OPENAI_SEED=7,
        OPENAI_MAX_OUTPUT_TOKENS="512",
    )
    def test_openai_option_resolvers_handle_positive_config_values(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 7.25)
        self.assertEqual(_resolve_openai_max_retries(), 3)
        self.assertEqual(_resolve_optional_openai_temperature(), 1.5)
        self.assertEqual(_resolve_optional_openai_seed(), 7)
        self.assertEqual(_resolve_optional_openai_max_output_tokens(), 512)

    @override_settings(OPENAI_TIMEOUT_SECONDS="6.5")
    def test_resolve_openai_timeout_seconds_returns_positive_string_value(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 6.5)

    @override_settings(OPENAI_TIMEOUT_SECONDS="0")
    def test_resolve_openai_timeout_seconds_uses_default_for_zero_string(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)

    @override_settings(
        OPENAI_TIMEOUT_SECONDS="",
        OPENAI_MAX_RETRIES="",
        OPENAI_TEMPERATURE="",
        OPENAI_SEED="",
        OPENAI_MAX_OUTPUT_TOKENS="",
    )
    def test_openai_option_resolvers_handle_blank_strings(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertIsNone(_resolve_optional_openai_seed())
        self.assertIsNone(_resolve_optional_openai_max_output_tokens())

    @override_settings(
        OPENAI_TIMEOUT_SECONDS="  ",
        OPENAI_MAX_RETRIES="  ",
        OPENAI_TEMPERATURE="  ",
        OPENAI_SEED="  ",
        OPENAI_MAX_OUTPUT_TOKENS="  ",
    )
    def test_openai_option_resolvers_handle_whitespace_strings(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertIsNone(_resolve_optional_openai_seed())
        self.assertIsNone(_resolve_optional_openai_max_output_tokens())

    @override_settings(
        OPENAI_TIMEOUT_SECONDS="invalid",
        OPENAI_MAX_RETRIES="invalid",
        OPENAI_TEMPERATURE="invalid",
        OPENAI_SEED="invalid",
        OPENAI_MAX_OUTPUT_TOKENS="invalid",
    )
    def test_openai_option_resolvers_handle_invalid_strings(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertIsNone(_resolve_optional_openai_seed())
        self.assertIsNone(_resolve_optional_openai_max_output_tokens())

    @override_settings(
        OPENAI_TIMEOUT_SECONDS=object(),
        OPENAI_MAX_RETRIES=object(),
        OPENAI_TEMPERATURE=object(),
        OPENAI_SEED=object(),
        OPENAI_MAX_OUTPUT_TOKENS=object(),
    )
    def test_openai_option_resolvers_handle_unsupported_types(self):
        self.assertEqual(_resolve_openai_timeout_seconds(), 30.0)
        self.assertEqual(_resolve_openai_max_retries(), 2)
        self.assertIsNone(_resolve_optional_openai_temperature())
        self.assertIsNone(_resolve_optional_openai_seed())
        self.assertIsNone(_resolve_optional_openai_max_output_tokens())

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS=True,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN=2.9,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX="6",
    )
    def test_openai_positive_setting_helpers_handle_valid_partitions(self):
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS",
                11,
            ),
            11,
        )
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN",
                11,
            ),
            2,
        )
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX",
                11,
            ),
            6,
        )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS="",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN="bad",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX="0",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=object(),
    )
    def test_openai_positive_setting_helpers_handle_invalid_partitions(self):
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS",
                11,
            ),
            11,
        )
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN",
                11,
            ),
            11,
        )
        self.assertEqual(
            _resolve_openai_positive_int_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX",
                11,
            ),
            11,
        )
        self.assertEqual(
            _resolve_positive_float_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
                1.5,
            ),
            1.5,
        )

        with override_settings(OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX=object()):
            self.assertEqual(
                _resolve_openai_positive_int_setting(
                    "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX",
                    11,
                ),
                11,
            )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=True,
    )
    def test_openai_positive_float_setting_handles_boolean(self):
        self.assertEqual(
            _resolve_positive_float_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
                1.5,
            ),
            1.5,
        )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO="2.5",
    )
    def test_openai_positive_float_setting_handles_positive_string(self):
        self.assertEqual(
            _resolve_positive_float_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
                1.5,
            ),
            2.5,
        )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO="",
    )
    def test_openai_positive_float_setting_handles_blank_string(self):
        self.assertEqual(
            _resolve_positive_float_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
                1.5,
            ),
            1.5,
        )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO="bad",
    )
    def test_openai_positive_float_setting_handles_invalid_string(self):
        self.assertEqual(
            _resolve_positive_float_setting(
                "OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO",
                1.5,
            ),
            1.5,
        )

    @override_settings(
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS=2,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN=20,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX=10,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=1.0,
    )
    def test_adaptive_max_output_tokens_partitions(self):
        self.assertIsNone(_resolve_adaptive_max_output_tokens(None))
        self.assertIsNone(_resolve_adaptive_max_output_tokens("   "))
        self.assertIsNone(_resolve_adaptive_max_output_tokens("x"))
        self.assertEqual(_resolve_adaptive_max_output_tokens("x" * 80), 20)

    @override_settings(
        OPENAI_TEMPERATURE="",
        OPENAI_SEED="",
        OPENAI_MAX_OUTPUT_TOKENS="",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS=2,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN=5,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX=50,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=1.0,
    )
    def test_common_generation_options_uses_adaptive_tokens_when_static_limit_missing(self):
        self.assertEqual(_resolve_common_generation_options("x" * 80), (None, None, 20))

    @override_settings(OPENAI_TEMPERATURE="", OPENAI_SEED="", OPENAI_MAX_OUTPUT_TOKENS="")
    def test_apply_generation_options_omits_none_values(self):
        self.assertEqual(
            _apply_generation_options(
                {},
                None,
                None,
                None,
                token_key="max_output_tokens",
            ),
            {},
        )

    def test_message_budget_content_helpers_partition_inputs(self):
        self.assertEqual(_extract_message_content_for_budget("raw message"), "raw message")
        self.assertEqual(
            _extract_message_content_for_budget({"content": {"a": 1}}),
            '{"a": 1}',
        )
        self.assertEqual(_extract_message_content_for_budget({"other": "missing"}), "")
        self.assertEqual(_extract_message_content_for_budget(123), "")
        self.assertEqual(
            _build_prompt_context_from_messages(
                [
                    {"role": "user", "content": "Hello"},
                    {"role": " ", "content": "No role"},
                    "skip",
                ]
            ),
            "user: Hello\nNo role",
        )

    @override_settings(OPENAI_MAX_OUTPUT_TOKENS=256)
    def test_response_generation_options_include_system_prompt_context(self):
        self.assertEqual(
            _build_response_generation_options(
                "Prompt",
                system_prompt="  System  ",
            ),
            {"max_output_tokens": 256},
        )

    def test_map_api_status_to_http_partitions(self):
        self.assertEqual(_map_api_status_to_http(404), 404)
        self.assertEqual(_map_api_status_to_http(429), 429)
        self.assertEqual(_map_api_status_to_http(408), 504)
        self.assertEqual(_map_api_status_to_http(504), 504)
        self.assertEqual(_map_api_status_to_http(418), 502)
        self.assertEqual(_map_api_status_to_http(None), 502)

    def test_normalize_chat_message_content_partitions(self):
        self.assertEqual(_normalize_chat_message_content("  ok  "), "ok")
        self.assertIsNone(_normalize_chat_message_content("   "))
        self.assertEqual(
            _normalize_chat_message_content(
                [
                    {"text": " A "},
                    {"content": "B"},
                    SimpleNamespace(text=" C "),
                    SimpleNamespace(content="D"),
                    {"text": "  "},
                    123,
                ]
            ),
            "A\nB\nC\nD",
        )
        self.assertIsNone(_normalize_chat_message_content([{"text": "  "}]))
        self.assertIsNone(_normalize_chat_message_content(123))

    @override_settings(
        OPENAI_TEMPERATURE=2,
        OPENAI_SEED="42",
        OPENAI_MAX_OUTPUT_TOKENS=256,
    )
    def test_generation_option_builders_map_tokens_to_endpoint_specific_keys(self):
        self.assertEqual(
            _build_response_generation_options("Extract this payload"),
            {"temperature": 2.0, "seed": 42, "max_output_tokens": 256},
        )
        self.assertEqual(
            _build_chat_generation_options(
                [{"role": "user", "content": "Summarize this payload"}]
            ),
            {"temperature": 2.0, "seed": 42, "max_completion_tokens": 256},
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://proxy.example.test/v1",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_build_client_from_signature_and_build_client_forward_base_url(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client

        direct_client = _build_client_from_signature(
            "direct-key",
            "https://direct.example.test/v1",
            9.5,
            3,
        )
        settings_client = _build_client()

        self.assertIs(direct_client, mock_client)
        self.assertIs(settings_client, mock_client)
        self.assertEqual(mock_openai.call_count, 2)
        mock_openai.assert_any_call(
            api_key="direct-key",
            base_url="https://direct.example.test/v1",
            timeout=9.5,
            max_retries=3,
        )
        mock_openai.assert_any_call(
            api_key="test-key",
            base_url="https://proxy.example.test/v1",
            timeout=30.0,
            max_retries=2,
        )

    def test_text_generation_provider_cache_uses_provider_created_while_locked(self):
        reset_text_generation_provider_cache()
        provider = OpenAITextGenerationProvider()

        class PopulateProviderLock:
            def __enter__(self):
                openai_client._TEXT_PROVIDER_SINGLETON = provider

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch.object(openai_client, "_TEXT_PROVIDER_LOCK", PopulateProviderLock()):
            self.assertIs(openai_client._get_text_generation_provider(), provider)

    @override_settings(OPENAI_API_KEY="test-key")
    def test_chat_completion_client_cache_uses_client_created_while_locked(self):
        reset_chat_completion_client_cache()
        client = Mock()

        class PopulateClientLock:
            def __enter__(self):
                openai_client._CHAT_COMPLETION_CLIENT_SINGLETON = client
                openai_client._CHAT_COMPLETION_CLIENT_SIGNATURE = (
                    openai_client._resolve_chat_completion_client_signature()
                )

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch.object(openai_client, "_CHAT_COMPLETION_CLIENT_LOCK", PopulateClientLock()), patch(
            "llm.services.openai_client._build_client"
        ) as mock_build_client:
            self.assertIs(_get_chat_completion_client(), client)

        mock_build_client.assert_not_called()

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

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_BASE_URL=" https://proxy.example.test/v1 ",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_builds_client_with_trimmed_base_url(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        result = generate_text("Say hi")

        self.assertEqual(result, "ok result")
        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://proxy.example.test/v1",
            timeout=30.0,
            max_retries=2,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TIMEOUT_SECONDS="45.5",
        OPENAI_MAX_RETRIES="4",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_builds_client_with_configured_timeout_and_retries(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        generate_text("Say hi")

        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=45.5,
            max_retries=4,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TIMEOUT_SECONDS="invalid",
        OPENAI_MAX_RETRIES="-9",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_builds_client_with_default_timeout_and_retries_on_invalid_config(
        self, mock_openai
    ):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        generate_text("Say hi")

        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TEMPERATURE="0.2",
        OPENAI_SEED="7",
        OPENAI_MAX_OUTPUT_TOKENS="333",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_passes_optional_generation_limits_when_configured(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        generate_text("Say hi")

        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="Say hi",
            temperature=0.2,
            seed=7,
            max_output_tokens=333,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_MAX_OUTPUT_TOKENS="",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS=10,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN=50,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX=200,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=1.0,
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_applies_adaptive_max_output_tokens_for_large_prompt(
        self, mock_openai
    ):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        generate_text("x" * 400)

        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="x" * 400,
            max_output_tokens=100,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TEMPERATURE="bad",
        OPENAI_SEED="invalid-seed",
        OPENAI_MAX_OUTPUT_TOKENS="-1",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_ignores_invalid_optional_generation_limits(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.return_value = Mock(output_text="ok result")

        generate_text("Say hi")

        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="Say hi",
        )

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_text_generation_provider_reuses_cached_client_for_same_settings(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = [
            Mock(output_text="first"),
            Mock(output_text="second"),
        ]
        provider = OpenAITextGenerationProvider()

        first_result = provider.generate_text("First prompt")
        second_result = provider.generate_text("Second prompt")

        self.assertEqual(first_result, "first")
        self.assertEqual(second_result, "second")
        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
        )
        self.assertEqual(mock_client.responses.create.call_count, 2)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_reuses_singleton_provider_client_for_same_settings(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = [
            Mock(output_text="first"),
            Mock(output_text="second"),
        ]

        first_result = generate_text("First prompt")
        second_result = generate_text("Second prompt")

        self.assertEqual(first_result, "first")
        self.assertEqual(second_result, "second")
        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
        )
        self.assertEqual(mock_client.responses.create.call_count, 2)

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_BASE_URL="https://proxy-a.example/v1",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_text_generation_provider_rebuilds_client_when_base_url_changes(self, mock_openai):
        first_client = Mock()
        second_client = Mock()
        mock_openai.side_effect = [first_client, second_client]
        first_client.responses.create.return_value = Mock(output_text="first")
        second_client.responses.create.return_value = Mock(output_text="second")
        provider = OpenAITextGenerationProvider()

        first_result = provider.generate_text("First prompt")
        with override_settings(OPENAI_BASE_URL="https://proxy-b.example/v1"):
            second_result = provider.generate_text("Second prompt")

        self.assertEqual(first_result, "first")
        self.assertEqual(second_result, "second")
        self.assertEqual(mock_openai.call_count, 2)
        first_call_kwargs = mock_openai.call_args_list[0].kwargs
        second_call_kwargs = mock_openai.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs["base_url"], "https://proxy-a.example/v1")
        self.assertEqual(second_call_kwargs["base_url"], "https://proxy-b.example/v1")

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

        self.assertEqual(exc_ctx.exception.status_code, 502)

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
    def test_generate_text_maps_api_status_401_to_502(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError("api status", status_code=401)

        with self.assertRaises(OpenAIUpstreamError) as exc_ctx:
            generate_text("Hello")

        self.assertEqual(exc_ctx.exception.status_code, 502)

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
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_falls_back_to_chat_completions_on_responses_404(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError(
            "not found",
            status_code=404,
        )
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="fallback result"))]
        )

        result = generate_text("Hello", system_prompt="Use strict JSON.")

        self.assertEqual(result, "fallback result")
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4.1-mini",
            input="Hello",
            instructions="Use strict JSON.",
        )
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Use strict JSON."},
                {"role": "user", "content": "Hello"},
            ],
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_SYSTEM_PROMPT="   ",
    )
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_fallback_omits_system_message_when_prompt_blank(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError(
            "not found",
            status_code=404,
        )
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="fallback result"))]
        )

        result = generate_text("Hello")

        self.assertEqual(result, "fallback result")
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.APIStatusError", new=DummyAPIStatusError)
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_text_fallback_raises_when_chat_choices_missing(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.responses.create.side_effect = DummyAPIStatusError(
            "not found",
            status_code=404,
        )
        mock_client.chat.completions.create.return_value = Mock(choices=[])

        with self.assertRaises(OpenAIServiceError):
            generate_text("Hello")

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

    def test_json_generation_service_compacts_upload_wrapper_payload_for_prompt(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        service.generate(
            {
                "status": "success",
                "message": "File uploaded successfully",
                "filename": "report.pdf",
                "size": 20480,
                "format": "pdf",
                "extracted": {
                    "Sheet1": [["name", "amount"], ["A", 10]],
                },
            }
        )

        text_provider.generate_text.assert_called_once()
        prompt = text_provider.generate_text.call_args.kwargs["prompt"]
        parsed_prompt = json.loads(prompt)
        self.assertEqual(
            parsed_prompt,
            {
                "filename": "report.pdf",
                "format": "pdf",
                "extracted": {
                    "Sheet1": [["name", "amount"], ["A", 10]],
                },
            },
        )

    def test_json_generation_service_compacts_nested_original_input_for_refinement_payload(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        service.generate(
            {
                "original_input_json": {
                    "status": "success",
                    "message": "File uploaded successfully",
                    "filename": "report.pdf",
                    "size": 20480,
                    "format": "pdf",
                    "extracted": {"Sheet1": [["name"], ["A"]]},
                    "user_prompt": "  Only keep paid invoices  ",
                },
                "previous_output_json": {"content_data": []},
                "validation_log": {"iteration": 1, "verdict": "invalid"},
            }
        )

        text_provider.generate_text.assert_called_once()
        prompt = text_provider.generate_text.call_args.kwargs["prompt"]
        parsed_prompt = json.loads(prompt)
        self.assertEqual(
            parsed_prompt["original_input_json"],
            {
                "filename": "report.pdf",
                "format": "pdf",
                "extracted": {"Sheet1": [["name"], ["A"]]},
                "user_prompt": "Only keep paid invoices",
            },
        )
        self.assertEqual(parsed_prompt["previous_output_json"], {"content_data": []})
        self.assertEqual(
            parsed_prompt["validation_log"],
            {"iteration": 1, "verdict": "invalid"},
        )

    def test_json_generation_service_drops_blank_user_prompt_when_compacting(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        service.generate(
            {
                "status": "success",
                "message": "File uploaded successfully",
                "filename": "report.pdf",
                "size": 20480,
                "format": "pdf",
                "extracted": {"Sheet1": [["name"], ["A"]]},
                "user_prompt": "   ",
            }
        )

        prompt = text_provider.generate_text.call_args.kwargs["prompt"]
        parsed_prompt = json.loads(prompt)
        self.assertNotIn("user_prompt", parsed_prompt)
        self.assertEqual(
            parsed_prompt,
            {
                "filename": "report.pdf",
                "format": "pdf",
                "extracted": {"Sheet1": [["name"], ["A"]]},
            },
        )

    @override_settings(
        LLM_PROMPT_MAX_CHARS=500,
        LLM_PROMPT_MAX_TABLES=1,
        LLM_PROMPT_MAX_ROWS_PER_TABLE=2,
        LLM_PROMPT_MAX_COLUMNS_PER_ROW=2,
        LLM_PROMPT_MAX_CELL_CHARS=5,
    )
    def test_json_generation_service_applies_prompt_budget_sampling_for_large_payload(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)
        large_rows = [["very-long-cell-value"] * 6 for _ in range(30)]

        service.generate(
            {
                "status": "success",
                "message": "File uploaded successfully",
                "filename": "report.pdf",
                "size": 20480,
                "format": "pdf",
                "extracted": {
                    "Sheet1": large_rows,
                    "Sheet2": large_rows,
                },
                "user_prompt": "keep important fields",
            }
        )

        prompt = text_provider.generate_text.call_args.kwargs["prompt"]
        parsed_prompt = json.loads(prompt)
        self.assertEqual(parsed_prompt["_prompt_budget"]["mode"], "sampled")
        self.assertEqual(len(parsed_prompt["extracted"]), 1)
        first_table_rows = parsed_prompt["extracted"]["Sheet1"]
        self.assertEqual(len(first_table_rows), 2)
        self.assertEqual(len(first_table_rows[0]), 2)
        self.assertEqual(first_table_rows[0][0], "very-...")

    @override_settings(
        LLM_PROMPT_MAX_CHARS=80,
        LLM_PROMPT_MAX_TABLES=1,
        LLM_PROMPT_MAX_ROWS_PER_TABLE=1,
        LLM_PROMPT_MAX_COLUMNS_PER_ROW=1,
        LLM_PROMPT_MAX_CELL_CHARS=5,
    )
    def test_json_generation_service_falls_back_to_summary_payload_when_budget_is_still_too_large(
        self,
    ):
        text_provider = Mock()
        text_provider.generate_text.return_value = '{"status":"ok"}'
        service = JsonGenerationService(text_provider=text_provider)

        service.generate(
            {
                "status": "success",
                "filename": "report.pdf",
                "format": "pdf",
                "extracted": {
                    "Sheet1": [["very-long-cell-value"] * 8 for _ in range(100)],
                    "Sheet2": [["very-long-cell-value"] * 8 for _ in range(100)],
                },
                "user_prompt": "y" * 400,
            }
        )

        prompt = text_provider.generate_text.call_args.kwargs["prompt"]
        parsed_prompt = json.loads(prompt)
        self.assertEqual(parsed_prompt["_prompt_budget"]["mode"], "summary")
        self.assertIn("extracted_summary", parsed_prompt)

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
            refinement_instruction=None,
            chat_context=None,
            ocr_context=None,
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
            refinement_instruction=None,
            chat_context=None,
            ocr_context=None,
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
            refinement_instruction=None,
            chat_context=None,
            ocr_context=None,
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
            refinement_instruction=None,
            chat_context=None,
            ocr_context=None,
        )
        json_generator.generate.assert_called_once_with(
            input_json={"name": "Pen", "price": 5000},
            system_prompt="Extraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_passes_refinement_instruction_when_provided(
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

        result = service.generate(
            {"sheet": "Sheet1"},
            custom_schema_id=None,
            refinement_instruction="Fix validation errors",
        )

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint=None,
            refinement_instruction="Fix validation errors",
            chat_context=None,
            ocr_context=None,
        )
        json_generator.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            system_prompt="Base prompt.\n\nExtraction prompt.",
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
            refinement_instruction=None,
            chat_context=None,
            ocr_context=None,
        )
        schema_prompt_source.get_prompt_fragment.assert_called_once_with("schema-1")
        json_generator.generate.assert_called_once_with(
            input_json={"name": "Pen", "price": 5000},
            system_prompt="Extraction prompt.",
        )

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_caches_schema_fragment_for_repeated_schema_id(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.side_effect = [{"status": "ok-1"}, {"status": "ok-2"}]
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

        first_result = service.generate({"sheet": "Sheet1"}, custom_schema_id="schema-1")
        second_result = service.generate({"sheet": "Sheet2"}, custom_schema_id="schema-1")

        self.assertEqual(first_result, {"status": "ok-1"})
        self.assertEqual(second_result, {"status": "ok-2"})
        self.assertEqual(schema_prompt_source.get_prompt_fragment.call_count, 1)

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_passes_ocr_context_from_input_json(
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

        result = service.generate(
            {
                "sheet": "Sheet1",
                "ocr_metadata": {
                    "confidence_score": 53.5,
                    "confidence_level": "low",
                    "document_type": "pdf",
                },
            }
        )

        self.assertEqual(result, {"status": "ok"})
        mock_build_extraction_prompt.assert_called_once_with(
            schema_hint=None,
            refinement_instruction=None,
            chat_context=None,
            ocr_context={
                "confidence_score": 53.5,
                "confidence_level": "low",
                "document_type": "pdf",
            },
        )
        schema_prompt_source.get_prompt_fragment.assert_not_called()
        self.assertEqual(json_generator.generate.call_count, 1)

    @patch("llm.services.generation_service.build_extraction_prompt")
    def test_llm_generation_service_fetches_schema_fragment_for_distinct_schema_ids(
        self, mock_build_extraction_prompt
    ):
        json_generator = Mock()
        json_generator.generate.side_effect = [{"status": "ok-1"}, {"status": "ok-2"}]
        schema_prompt_source = Mock()
        schema_prompt_source.get_prompt_fragment.side_effect = [
            "Prompt A",
            "Prompt B",
        ]
        mock_build_extraction_prompt.return_value = "Extraction prompt."
        service = LlmGenerationService(
            json_generator=json_generator,
            schema_prompt_source=schema_prompt_source,
            base_system_prompt_provider=lambda: "",
        )

        service.generate({"sheet": "Sheet1"}, custom_schema_id="schema-a")
        service.generate({"sheet": "Sheet2"}, custom_schema_id="schema-b")

        self.assertEqual(schema_prompt_source.get_prompt_fragment.call_count, 2)
        self.assertEqual(
            schema_prompt_source.get_prompt_fragment.call_args_list[0].args[0],
            "schema-a",
        )
        self.assertEqual(
            schema_prompt_source.get_prompt_fragment.call_args_list[1].args[0],
            "schema-b",
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
    def setUp(self):
        super().setUp()
        reset_chat_completion_client_cache()

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

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_MAX_OUTPUT_TOKENS="",
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_THRESHOLD_CHARS=10,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MIN=50,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_MAX=200,
        OPENAI_ADAPTIVE_MAX_OUTPUT_TOKENS_RATIO=1.0,
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_applies_adaptive_max_completion_tokens_for_large_history(
        self, mock_openai
    ):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="ok"))]
        )
        messages = [{"role": "user", "content": "y" * 400}]

        generate_chat_response(messages)

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4.1-mini",
            messages=messages,
            max_completion_tokens=102,
        )

    @override_settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-4.1-mini",
        OPENAI_TEMPERATURE="0.4",
        OPENAI_SEED="99",
        OPENAI_MAX_OUTPUT_TOKENS="450",
    )
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_passes_optional_generation_limits_when_configured(
        self, mock_openai
    ):
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
            temperature=0.4,
            seed=99,
            max_completion_tokens=450,
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

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_reuses_cached_chat_client_within_same_runtime(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="ok"))]
        )

        generate_chat_response([{"role": "user", "content": "Halo"}])
        generate_chat_response([{"role": "user", "content": "Halo lagi"}])

        mock_openai.assert_called_once()
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini")
    @patch("llm.services.openai_client.OpenAI")
    def test_generate_chat_response_normalizes_list_content_chunks(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[
                Mock(
                    message=Mock(
                        content=[
                            {"text": " Halo "},
                            {"content": "Dunia"},
                            SimpleNamespace(text=" dari "),
                            SimpleNamespace(content="Chat"),
                            {"text": "   "},
                        ]
                    )
                )
            ]
        )

        result = generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(result, "Halo\nDunia\ndari\nChat")

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
    def test_generate_chat_response_maps_authentication_error_to_502(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = DummyAuthenticationError("bad auth")

        with self.assertRaises(OpenAIUpstreamError) as ctx:
            generate_chat_response([{"role": "user", "content": "Halo"}])

        self.assertEqual(ctx.exception.status_code, 502)

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


class GenerateStreamingChatResponseTest(SimpleTestCase):
    def setUp(self):
        super().setUp()
        reset_chat_completion_client_cache()

    def test_negative_raises_value_error_for_empty_messages(self):
        with self.assertRaises(ValueError):
            next(generate_streaming_chat_response([]))

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini", OPENAI_BASE_URL="")
    @patch("llm.services.openai_client.OpenAI")
    def test_negative_skips_chunks_with_no_delta_content(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        bad_chunk = Mock(choices=[])
        mock_stream = Mock()
        mock_stream.__iter__ = Mock(return_value=iter([bad_chunk]))
        mock_stream.close = Mock()
        mock_client.chat.completions.create.return_value = mock_stream

        result = list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(result, [])

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini", OPENAI_BASE_URL="")
    @patch("llm.services.openai_client.OpenAI")
    def test_positive_yields_delta_content_from_chunks(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        good_chunk = Mock()
        good_chunk.choices = [Mock(delta=Mock(content="Hello"))]
        mock_stream = Mock()
        mock_stream.__iter__ = Mock(return_value=iter([good_chunk]))
        mock_stream.close = Mock()
        mock_client.chat.completions.create.return_value = mock_stream

        result = list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        self.assertEqual(result, ["Hello"])

    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-4.1-mini", OPENAI_BASE_URL="")
    @patch("llm.services.openai_client.OpenAI")
    def test_positive_builds_client_without_base_url(self, mock_openai):
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_stream = Mock()
        mock_stream.__iter__ = Mock(return_value=iter([]))
        mock_stream.close = Mock()
        mock_client.chat.completions.create.return_value = mock_stream

        list(generate_streaming_chat_response([{"role": "user", "content": "Hi"}]))

        mock_openai.assert_called_once_with(
            api_key="test-key",
            timeout=30.0,
            max_retries=2,
        )
