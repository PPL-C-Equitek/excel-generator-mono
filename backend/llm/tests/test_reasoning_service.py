import json

from django.test import SimpleTestCase, override_settings
from unittest.mock import Mock, patch

from llm.services.reasoning_service import (
    FALLBACK_FINAL_ANSWER,
    FALLBACK_REASONING_STEP,
    FALLBACK_THINKING_LOG,
    LlmReasoningService,
    TextGenerationProvider,
    _collect_steps_from_lines,
    _extract_braced_json_candidate,
    _extract_json_from_fenced_blocks,
    _parse_structured_reasoning_object,
    _extract_step_text,
    _fallback_narrative_steps,
    get_base_system_prompt,
    _get_positive_int_setting,
    _split_labeled_line,
    _try_parse_json_candidate,
    generate_conversion_reasoning_response,
    generate_reasoning_response,
    parse_reasoning_response,
    validate_reasoning_response,
)
from llm.services.openai_client import OpenAIServiceError


class LlmReasoningServiceTest(SimpleTestCase):
    @override_settings(OPENAI_SYSTEM_PROMPT=None)
    def test_get_base_system_prompt_returns_empty_string_for_non_string_setting(self):
        result = get_base_system_prompt()

        self.assertEqual(result, "")

    # Positive
    def test_reasoning_service_returns_valid_reasoning_payload(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": " Total payment is Rp1.250.000. ",
                "reasoning_steps": [
                    " Identify the total amount. ",
                    " Confirm it is the final payable total. ",
                ],
                "thinking_log": " Summarized the invoice total for display. ",
            }
        )
        service = LlmReasoningService(
            text_provider=text_provider,
            base_system_prompt_provider=lambda: "Base prompt.",
            reasoning_system_prompt_provider=lambda: "Return strict reasoning JSON.",
        )

        result = service.generate("Summarize this invoice")

        self.assertEqual(
            result,
            {
                "final_answer": "Total payment is Rp1.250.000.",
                "reasoning_steps": [
                    "Identify the total amount.",
                    "Confirm it is the final payable total.",
                ],
                "thinking_log": "Summarized the invoice total for display.",
            },
        )
        text_provider.generate_text.assert_called_once_with(
            prompt="Summarize this invoice",
            system_prompt="Base prompt.\n\nReturn strict reasoning JSON.",
        )

    # Negative
    def test_reasoning_service_rejects_empty_prompt(self):
        service = LlmReasoningService(text_provider=Mock())

        with self.assertRaises(ValueError):
            service.generate("   ")

    # Negative
    def test_reasoning_service_falls_back_for_non_json_output(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = "not valid json"
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["reasoning_steps"], [FALLBACK_REASONING_STEP])
        self.assertEqual(result["final_answer"], FALLBACK_FINAL_ANSWER)
        self.assertEqual(result["thinking_log"], FALLBACK_THINKING_LOG)

    # Negative
    def test_reasoning_service_falls_back_for_non_object_json_output(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = '["invalid"]'
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["reasoning_steps"], [FALLBACK_REASONING_STEP])
        self.assertEqual(result["final_answer"], FALLBACK_FINAL_ANSWER)
        self.assertEqual(result["thinking_log"], FALLBACK_THINKING_LOG)

    # Positive
    def test_reasoning_service_parses_step_label_format(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = (
            "Final Answer: Total payment is Rp1.250.000.\n"
            "Step 1: Identify total from invoice summary.\n"
            "Step 2: Confirm no additional fees.\n"
            "Thinking Log: Parsed step-by-step summary for output."
        )
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["final_answer"], "Total payment is Rp1.250.000.")
        self.assertEqual(
            result["reasoning_steps"],
            [
                "Identify total from invoice summary.",
                "Confirm no additional fees.",
            ],
        )
        self.assertEqual(
            result["thinking_log"],
            "Parsed step-by-step summary for output.",
        )

    # Positive
    def test_reasoning_service_parses_numbering_and_bullet_format(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = (
            "Answer: Totals are validated.\n"
            "1. Read subtotal row.\n"
            "2) Add tax row.\n"
            "- Verify grand total row."
        )
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["final_answer"], "Totals are validated.")
        self.assertEqual(
            result["reasoning_steps"],
            [
                "Read subtotal row.",
                "Add tax row.",
                "Verify grand total row.",
            ],
        )

    # Edge
    def test_reasoning_service_parses_narrative_format_when_no_markers_exist(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = (
            "I checked the summary section. "
            "The grand total line is Rp1.250.000. "
            "No extra adjustment line appears."
        )
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["final_answer"], FALLBACK_FINAL_ANSWER)
        self.assertEqual(result["reasoning_steps"], [FALLBACK_REASONING_STEP])
        self.assertEqual(result["thinking_log"], FALLBACK_THINKING_LOG)

    # Edge
    def test_reasoning_service_parses_json_inside_code_fence(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = (
            "Here is the output:\n"
            "```json\n"
            '{"final_answer":"Answer","reasoning_steps":["Step one"],"thinking_log":"Summary"}\n'
            "```"
        )
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(
            result,
            {
                "final_answer": "Answer",
                "reasoning_steps": ["Step one"],
                "thinking_log": "Summary",
            },
        )

    # Negative
    def test_reasoning_service_rejects_blank_reasoning_step(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": "Answer",
                "reasoning_steps": ["Valid", "   "],
                "thinking_log": "Summary",
            }
        )
        service = LlmReasoningService(text_provider=text_provider)

        with self.assertRaises(OpenAIServiceError):
            service.generate("Summarize this invoice")

    # Negative
    def test_reasoning_service_rejects_empty_reasoning_steps(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": "Answer",
                "reasoning_steps": [],
                "thinking_log": "Summary",
            }
        )
        service = LlmReasoningService(text_provider=text_provider)

        with self.assertRaises(OpenAIServiceError):
            service.generate("Summarize this invoice")

    def test_reasoning_service_rejects_blank_thinking_log(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": "Answer",
                "reasoning_steps": ["Valid"],
                "thinking_log": "   ",
            }
        )
        service = LlmReasoningService(text_provider=text_provider)

        with self.assertRaises(OpenAIServiceError):
            service.generate("Summarize this invoice")

    # Edge
    @override_settings(
        LLM_REASONING_OUTPUT_TEXT_MAX_CHARS=2000,
        LLM_REASONING_FINAL_ANSWER_MAX_CHARS=10,
        LLM_REASONING_THINKING_LOG_MAX_CHARS=12,
        LLM_REASONING_STEP_MAX_CHARS=8,
        LLM_REASONING_STEPS_MAX_ITEMS=2,
    )
    def test_reasoning_service_applies_safe_truncation_limits(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": "A" * 100,
                "reasoning_steps": ["B" * 50, "C" * 50, "D" * 50],
                "thinking_log": "E" * 100,
            }
        )
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertEqual(result["final_answer"], "A" * 10)
        self.assertEqual(result["thinking_log"], "E" * 12)
        self.assertEqual(result["reasoning_steps"], ["B" * 8, "C" * 8])

    # Edge
    def test_reasoning_service_falls_back_for_blank_output(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = "   "
        service = LlmReasoningService(text_provider=text_provider)

        result = service.generate("Summarize this invoice")

        self.assertTrue(result["final_answer"])
        self.assertEqual(len(result["reasoning_steps"]), 1)
        self.assertTrue(result["thinking_log"])

    # Edge
    def test_reasoning_service_omits_system_prompt_when_all_prompts_blank(self):
        text_provider = Mock()
        text_provider.generate_text.return_value = json.dumps(
            {
                "final_answer": "Answer",
                "reasoning_steps": ["Step one"],
                "thinking_log": "Summary",
            }
        )
        service = LlmReasoningService(
            text_provider=text_provider,
            base_system_prompt_provider=lambda: "   ",
            reasoning_system_prompt_provider=lambda: "   ",
        )

        result = service.generate("Summarize this invoice")

        self.assertEqual(
            result,
            {
                "final_answer": "Answer",
                "reasoning_steps": ["Step one"],
                "thinking_log": "Summary",
            },
        )
        text_provider.generate_text.assert_called_once_with(
            prompt="Summarize this invoice"
        )


class ReasoningParserCoverageTest(SimpleTestCase):
    def test_extract_json_from_fenced_blocks_supports_whitespace_and_crlf(self):
        blocks = _extract_json_from_fenced_blocks(
            """
            ```   json   \r\n
            {"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}
            ```
            """
        )

        self.assertEqual(
            blocks,
            ['{"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}'],
        )

    def test_extract_json_from_fenced_blocks_ignores_non_json_language_and_empty_blocks(self):
        blocks = _extract_json_from_fenced_blocks(
            """
            ```python
            print('hello')
            ```
            ```json
            
            ```
            """
        )

        self.assertEqual(blocks, [])

    def test_extract_json_from_fenced_blocks_stops_gracefully_on_unclosed_fence(self):
        blocks = _extract_json_from_fenced_blocks("```json\n{\"a\": 1}")

        self.assertEqual(blocks, [])

    def test_extract_json_from_fenced_blocks_supports_inline_json_fence_without_newline(self):
        blocks = _extract_json_from_fenced_blocks(
            "prefix ```json{\"final_answer\":\"A\",\"reasoning_steps\":[\"S1\"],\"thinking_log\":\"T\"}``` suffix"
        )

        self.assertEqual(
            blocks,
            ['{"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}'],
        )

    def test_get_positive_int_setting_falls_back_to_default_for_invalid_values(self):
        with override_settings(LLM_REASONING_STEP_MAX_CHARS="invalid"):
            result = _get_positive_int_setting("LLM_REASONING_STEP_MAX_CHARS", 123)

        self.assertEqual(result, 123)

    def test_try_parse_json_candidate_returns_none_for_blank_text(self):
        self.assertIsNone(_try_parse_json_candidate("   "))

    def test_extract_braced_json_candidate_returns_trimmed_candidate(self):
        text = "prefix {\"final_answer\":\"ok\"} suffix"

        result = _extract_braced_json_candidate(text)

        self.assertEqual(result, '{"final_answer":"ok"}')

    def test_parse_reasoning_response_handles_none_input_with_fallback(self):
        result = parse_reasoning_response(None)

        self.assertTrue(result["final_answer"])
        self.assertEqual(len(result["reasoning_steps"]), 1)
        self.assertTrue(result["thinking_log"])

    def test_parse_reasoning_response_uses_braced_embedded_json(self):
        result = parse_reasoning_response(
            'raw output -> {"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"} <- done'
        )

        self.assertEqual(
            result,
            {
                "final_answer": "A",
                "reasoning_steps": ["S1"],
                "thinking_log": "T",
            },
        )

    def test_parse_reasoning_response_uses_fast_path_for_direct_json_object(self):
        result = parse_reasoning_response(
            '{"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}'
        )

        self.assertEqual(
            result,
            {
                "final_answer": "A",
                "reasoning_steps": ["S1"],
                "thinking_log": "T",
            },
        )

    def test_parse_reasoning_response_braced_invalid_json_uses_safe_placeholders(self):
        result = parse_reasoning_response("{not valid json}")

        self.assertEqual(result["final_answer"], FALLBACK_FINAL_ANSWER)
        self.assertEqual(result["reasoning_steps"], [FALLBACK_REASONING_STEP])
        self.assertEqual(result["thinking_log"], FALLBACK_THINKING_LOG)

    def test_parse_structured_reasoning_object_uses_direct_json_when_enabled(self):
        result = _parse_structured_reasoning_object(
            '{"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}',
        )

        self.assertEqual(
            result,
            {
                "final_answer": "A",
                "reasoning_steps": ["S1"],
                "thinking_log": "T",
            },
        )

    def test_parse_reasoning_response_skips_non_dict_fenced_json_then_uses_next_dict(self):
        result = parse_reasoning_response(
            """
            ```json
            ["not-a-dict"]
            ```
            ```json
            {"final_answer":"A","reasoning_steps":["S1"],"thinking_log":"T"}
            ```
            """
        )

        self.assertEqual(result["final_answer"], "A")
        self.assertEqual(result["reasoning_steps"], ["S1"])
        self.assertEqual(result["thinking_log"], "T")

    @override_settings(LLM_REASONING_STEPS_MAX_ITEMS=1)
    def test_parse_reasoning_response_respects_step_match_max_items(self):
        result = parse_reasoning_response(
            """
            Step 1: Read subtotal.
            Step 2: Add tax.
            Final Answer: Done.
            """
        )

        self.assertEqual(result["reasoning_steps"], ["Read subtotal."])

    @override_settings(LLM_REASONING_STEPS_MAX_ITEMS=1)
    def test_parse_reasoning_response_respects_section_step_max_items(self):
        result = parse_reasoning_response(
            """
            Steps:
            Read subtotal row.
            Add tax row.
            Final Answer: Done.
            Thinking Log: section mode.
            """
        )

        self.assertEqual(result["reasoning_steps"], ["Read subtotal row."])
        self.assertEqual(result["final_answer"], "Done.")

    def test_parse_reasoning_response_stops_section_steps_on_final_or_thinking_markers(self):
        result = parse_reasoning_response(
            """
            Steps:
            Collect values.
            Final Answer: Completed.
            Thinking Log: summary.
            """
        )

        self.assertEqual(result["reasoning_steps"], ["Collect values."])

    def test_parse_reasoning_response_handles_empty_step_from_step_marker_line(self):
        result = parse_reasoning_response(
            """
            1.   
            2. Keep this step.
            """
        )

        self.assertIn("Keep this step.", result["reasoning_steps"])

    def test_collect_steps_from_lines_skips_whitespace_only_step_match(self):
        steps = _collect_steps_from_lines(
            ["1.   ", "2. Keep this step."],
            max_steps=5,
            max_step_chars=100,
        )

        self.assertEqual(steps, ["Keep this step."])

    def test_collect_steps_from_lines_handles_zero_max_step_chars(self):
        steps = _collect_steps_from_lines(
            ["1. Keep this step."],
            max_steps=5,
            max_step_chars=0,
        )

        self.assertEqual(steps, [])

    def test_extract_step_text_returns_none_for_blank_or_invalid_step_prefix(self):
        self.assertIsNone(_extract_step_text("   "))
        self.assertIsNone(_extract_step_text("Step : missing number"))
        self.assertIsNone(_extract_step_text("12 no-delimiter"))
        self.assertIsNone(_extract_step_text("1   "))

    def test_parse_reasoning_response_supports_hyphen_labeled_fields(self):
        result = parse_reasoning_response(
            """
            Final Answer - Done safely.
            Thinking Log - Parsed with separator dash.
            Step 1: Keep deterministic parsing.
            """
        )

        self.assertEqual(result["final_answer"], "Done safely.")
        self.assertEqual(result["thinking_log"], "Parsed with separator dash.")

    def test_split_labeled_line_skips_empty_label_then_uses_next_separator(self):
        label, value = _split_labeled_line("   :ignored - usable value")

        self.assertEqual(label, ":ignored")
        self.assertEqual(value, "usable value")

    @override_settings(LLM_REASONING_STEPS_MAX_ITEMS=1)
    def test_parse_reasoning_response_narrative_limits_steps_and_skips_empty_sentences(self):
        result = parse_reasoning_response("First sentence.   Second sentence?")

        self.assertEqual(result["final_answer"], FALLBACK_FINAL_ANSWER)
        self.assertEqual(result["reasoning_steps"], [FALLBACK_REASONING_STEP])
        self.assertEqual(result["thinking_log"], FALLBACK_THINKING_LOG)

    @patch("llm.services.reasoning_service._get_positive_int_setting")
    def test_parse_reasoning_response_handles_empty_step_inside_section_when_step_truncates_empty(
        self,
        mock_get_positive_int_setting,
    ):
        def _setting(name, default):
            if name == "LLM_REASONING_STEP_MAX_CHARS":
                return 0
            if name == "LLM_REASONING_STEPS_MAX_ITEMS":
                return 2
            return default

        mock_get_positive_int_setting.side_effect = _setting
        result = parse_reasoning_response(
            """
            Steps:
            Collect values.
            Final Answer: Done.
            Thinking Log: Summary.
            """
        )

        self.assertTrue(result["reasoning_steps"])

    def test_parse_reasoning_response_continues_when_braced_candidate_is_not_json_object(self):
        result = parse_reasoning_response(
            "Final Answer: Completed. Payload: {not valid json}. Thinking Log: done."
        )

        self.assertEqual(result["final_answer"], "Completed. Payload: {not valid json}. Thinking Log: done.")

    @patch("llm.services.reasoning_service.SENTENCE_SPLIT_RE")
    def test_fallback_narrative_steps_skips_empty_sentences(self, mock_sentence_split_re):
        mock_sentence_split_re.split.return_value = ["", "First sentence.", ""]
        steps = _fallback_narrative_steps("placeholder", max_steps=5, max_step_chars=100)

        self.assertEqual(steps, ["First sentence."])

    @patch("llm.services.reasoning_service.SENTENCE_SPLIT_RE")
    def test_fallback_narrative_steps_uses_raw_text_when_split_produces_no_steps(
        self,
        mock_sentence_split_re,
    ):
        mock_sentence_split_re.split.return_value = ["", ""]
        steps = _fallback_narrative_steps("Raw fallback text", max_steps=5, max_step_chars=100)

        self.assertEqual(steps, ["Raw fallback text"])

    @patch("llm.services.reasoning_service.SENTENCE_SPLIT_RE")
    def test_fallback_narrative_steps_returns_empty_for_blank_raw_text(
        self,
        mock_sentence_split_re,
    ):
        mock_sentence_split_re.split.return_value = ["", ""]
        steps = _fallback_narrative_steps("   ", max_steps=5, max_step_chars=100)

        self.assertEqual(steps, [])

    def test_fallback_narrative_steps_stops_when_max_steps_reached(self):
        steps = _fallback_narrative_steps(
            "First sentence. Second sentence.",
            max_steps=1,
            max_step_chars=100,
        )

        self.assertEqual(steps, ["First sentence."])

    @patch("llm.services.reasoning_service._fallback_narrative_steps", return_value=[])
    @patch("llm.services.reasoning_service._collect_steps_from_lines", return_value=[])
    def test_parse_reasoning_response_uses_last_resort_reasoning_step_when_no_steps(
        self,
        _mock_collect,
        _mock_fallback,
    ):
        result = parse_reasoning_response("No parseable structure")

        self.assertEqual(len(result["reasoning_steps"]), 1)
        self.assertTrue(result["reasoning_steps"][0])

    def test_validate_reasoning_response_rejects_non_object_payload(self):
        with self.assertRaises(OpenAIServiceError):
            validate_reasoning_response(["not", "an", "object"])

    def test_validate_reasoning_response_accepts_reasoning_steps_string(self):
        result = validate_reasoning_response(
            {
                "final_answer": "Done",
                "reasoning_steps": "Single step",
                "thinking_log": "Summary",
            }
        )

        self.assertEqual(result["reasoning_steps"], ["Single step"])

    @patch("llm.services.reasoning_service._get_positive_int_setting", return_value=0)
    def test_validate_reasoning_response_raises_when_step_list_becomes_empty_after_limit(
        self,
        _mock_max_setting,
    ):
        with self.assertRaises(OpenAIServiceError):
            validate_reasoning_response(
                {
                    "final_answer": "Done",
                    "reasoning_steps": ["Step 1"],
                    "thinking_log": "Summary",
                }
            )

    def test_generate_reasoning_response_delegates_to_reasoning_service(self):
        reasoning_service = Mock(spec=LlmReasoningService)
        reasoning_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }

        result = generate_reasoning_response(
            reasoning_service=reasoning_service,
            prompt="Summarize conversion",
        )

        self.assertEqual(result["final_answer"], "Answer")
        reasoning_service.generate.assert_called_once_with(prompt="Summarize conversion")

    @patch("llm.services.reasoning_service.build_conversion_reasoning_prompt")
    def test_generate_conversion_reasoning_response_builds_prompt_and_delegates(
        self,
        mock_build_prompt,
    ):
        mock_build_prompt.return_value = "compiled conversion prompt"
        reasoning_service = Mock(spec=LlmReasoningService)
        reasoning_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }

        result = generate_conversion_reasoning_response(
            reasoning_service=reasoning_service,
            input_json={"document_info": {"filename": "input.xlsx"}},
            output_json={"status": "ok"},
        )

        self.assertEqual(result["thinking_log"], "Summary")
        mock_build_prompt.assert_called_once_with(
            input_json={"document_info": {"filename": "input.xlsx"}},
            output_json={"status": "ok"},
            file_name="unknown",
            document_type="unknown",
        )
        reasoning_service.generate.assert_called_once_with(prompt="compiled conversion prompt")

    def test_text_generation_provider_protocol_method_returns_ellipsis(self):
        result = TextGenerationProvider.generate_text(object(), "prompt")

        self.assertIsNone(result)
