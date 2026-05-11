from django.test import SimpleTestCase
from django.test import override_settings
from types import SimpleNamespace
from uuid import uuid4

from django.utils import timezone

from llm.serializers import (
    LlmGenerateRequestSerializer,
    LlmGenerateResponseSerializer,
    LlmReasoningRequestSerializer,
    LlmReasoningResponseSerializer,
    SendMessageRequestSerializer,
    ThinkingLogItemSerializer,
    _safe_thinking_log_summary,
)
class LlmReasoningSerializerTest(SimpleTestCase):
    # Positive
    def test_reasoning_request_serializer_accepts_valid_payload(self):
        serializer = LlmReasoningRequestSerializer(
            data={"prompt": "Summarize this invoice"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["prompt"], "Summarize this invoice")

    # Negative
    def test_reasoning_request_serializer_rejects_model_field(self):
        serializer = LlmReasoningRequestSerializer(
            data={"prompt": "Summarize this invoice", "model": "gpt-4.1-mini"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("model", serializer.errors)

    # Edge
    def test_reasoning_response_serializer_rejects_empty_reasoning_steps(self):
        serializer = LlmReasoningResponseSerializer(
            data={
                "final_answer": "Answer",
                "reasoning_steps": [],
                "thinking_log": "Summary",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("reasoning_steps", serializer.errors)


class LlmGenerateSerializerTest(SimpleTestCase):
    def test_generate_request_serializer_accepts_json_object(self):
        serializer = LlmGenerateRequestSerializer(data={"input_json": {"sheet": "Sheet1"}})

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_request_serializer_accepts_json_array(self):
        serializer = LlmGenerateRequestSerializer(data={"input_json": [{"row": 1}]})

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_request_serializer_rejects_non_object_or_array(self):
        serializer = LlmGenerateRequestSerializer(data={"input_json": "not-json-object"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("input_json", serializer.errors)

    def test_generate_request_serializer_rejects_model_field(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}, "model": "gpt-4.1-mini"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("model", serializer.errors)

    def test_generate_request_serializer_accepts_valid_session_id(self):
        session_id = uuid4()
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}, "session_id": str(session_id)}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["session_id"], session_id)

    def test_generate_request_serializer_allows_missing_session_id(self):
        serializer = LlmGenerateRequestSerializer(data={"input_json": {"sheet": "Sheet1"}})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("session_id", serializer.validated_data)

    def test_generate_request_serializer_rejects_invalid_session_id(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}, "session_id": "not-a-uuid"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("session_id", serializer.errors)

    def test_generate_response_serializer_accepts_session_and_output_ids(self):
        chat_id = uuid4()
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"sheet": "Sheet1"},
                "session_id": str(uuid4()),
                "chat_id": str(chat_id),
                "output_id": str(uuid4()),
                "reasoning": None,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.data["chat_id"], str(chat_id))

    def test_generate_request_serializer_accepts_include_reasoning(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}, "include_reasoning": False}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["include_reasoning"])

    def test_generate_request_serializer_defaults_refinement_enabled_true(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.validated_data["refinement"]["enabled"])

    def test_generate_request_serializer_accepts_refinement_payload(self):
        serializer = LlmGenerateRequestSerializer(
            data={
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 2,
                    "early_exit_on_valid": False,
                },
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.validated_data["refinement"]["enabled"])
        self.assertEqual(serializer.validated_data["refinement"]["max_iterations"], 2)
        self.assertFalse(serializer.validated_data["refinement"]["early_exit_on_valid"])

    def test_generate_request_serializer_rejects_refinement_max_iterations_above_cap(self):
        serializer = LlmGenerateRequestSerializer(
            data={
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 4,
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement", serializer.errors)

    @override_settings(
        LLM_REFINEMENT_DEFAULT_MAX_ITER="invalid-default",
        LLM_REFINEMENT_MAX_ITER_CAP=5,
    )
    def test_generate_request_serializer_uses_safe_default_when_setting_invalid(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["refinement"]["max_iterations"], 3)

    @override_settings(
        LLM_REFINEMENT_DEFAULT_MAX_ITER="7",
        LLM_REFINEMENT_MAX_ITER_CAP="9",
    )
    def test_generate_request_serializer_uses_numeric_string_default_from_settings(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["refinement"]["max_iterations"], 7)

    @override_settings(LLM_REFINEMENT_MAX_ITER_CAP="5")
    def test_generate_request_serializer_applies_numeric_string_cap_from_settings(self):
        serializer = LlmGenerateRequestSerializer(
            data={
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 6,
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement", serializer.errors)

    def test_generate_response_serializer_allows_null_reasoning(self):
        serializer = LlmGenerateResponseSerializer(
            data={"output_json": {"status": "ok"}, "reasoning": None}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_response_serializer_rejects_reasoning_keys_inside_output_json(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {
                    "headers": [],
                    "rows": [],
                    "reasoning_steps": ["not allowed"],
                },
                "reasoning": None,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("output_json", serializer.errors)

    def test_generate_response_serializer_allows_list_output_json(self):
        serializer = LlmGenerateResponseSerializer(
            data={"output_json": [["row-1"]], "reasoning": None}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_response_serializer_accepts_refinement_fields(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {
                    "document_info": {"source_type": "Excel", "filename": "test.xlsx"},
                    "summary": {"total_tables": 1},
                    "content_data": [
                        {
                            "table_name": "Sheet1",
                            "headers": ["name"],
                            "rows": [{"name": "A"}],
                        }
                    ],
                },
                "reasoning": {
                    "final_answer": "Done",
                    "reasoning_steps": ["Validated schema."],
                    "thinking_log": "Refined output.",
                },
                "raw_json": {"status": "draft"},
                "validated_json": {"status": "valid"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "valid",
                    "errors": [],
                    "warnings": [],
                    "summary": "Output passed strict export schema validation.",
                },
                "refinement_meta": {
                    "iterations_run": 1,
                    "max_iterations": 3,
                    "early_exit_triggered": True,
                    "final_status": "valid",
                },
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_response_serializer_rejects_non_object_validation_log(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": "invalid",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_with_missing_keys(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "errors": [],
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_when_warnings_not_list(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": [],
                    "warnings": "not-a-list",
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_issue_item_when_not_object(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": ["not-object"],
                    "warnings": [],
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_issue_with_blank_required_field(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": [{"path": " ", "message": "bad", "severity": "error"}],
                    "warnings": [],
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_with_invalid_verdict(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "maybe",
                    "errors": [],
                    "warnings": [],
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_with_non_positive_iteration(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 0,
                    "verdict": "invalid",
                    "errors": [],
                    "warnings": [],
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_with_blank_summary(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": [],
                    "warnings": [],
                    "summary": "   ",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_accepts_validation_log_with_structured_issue_items(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": [{"path": "$.x", "message": "bad", "severity": "error"}],
                    "warnings": [{"path": "$.y", "message": "warn", "severity": "warning"}],
                    "summary": "invalid",
                },
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_response_serializer_rejects_validation_log_issue_without_required_fields(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validation_log": {
                    "iteration": 1,
                    "verdict": "invalid",
                    "errors": [{"path": "$.x", "severity": "error"}],
                    "warnings": [],
                    "summary": "invalid",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("validation_log", serializer.errors)

    def test_generate_response_serializer_rejects_non_object_refinement_meta(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": "invalid",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    def test_generate_response_serializer_rejects_refinement_meta_with_missing_keys(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": {"iterations_run": 1},
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    def test_generate_response_serializer_rejects_refinement_meta_with_non_positive_iterations_run(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": {
                    "iterations_run": 0,
                    "max_iterations": 3,
                    "early_exit_triggered": False,
                    "final_status": "failed",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    def test_generate_response_serializer_rejects_refinement_meta_with_non_positive_max_iterations(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": {
                    "iterations_run": 1,
                    "max_iterations": 0,
                    "early_exit_triggered": False,
                    "final_status": "failed",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    def test_generate_response_serializer_rejects_refinement_meta_with_non_boolean_early_exit(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": {
                    "iterations_run": 1,
                    "max_iterations": 1,
                    "early_exit_triggered": "no",
                    "final_status": "failed",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    # Positive
    def test_positive_generate_response_serializer_accepts_minimal_refinement_visible_payload(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "validated_json": {"status": "ok"},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    # Negative
    def test_negative_generate_response_serializer_rejects_invalid_refinement_meta_final_status(self):
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"status": "ok"},
                "refinement_meta": {
                    "iterations_run": 1,
                    "max_iterations": 3,
                    "early_exit_triggered": True,
                    "final_status": "unknown-status",
                },
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("refinement_meta", serializer.errors)

    # Edge
    def test_edge_generate_request_serializer_defaults_refinement_payload_when_omitted(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("refinement", serializer.validated_data)
        self.assertIn("max_iterations", serializer.validated_data["refinement"])


class ThinkingLogSerializerTest(SimpleTestCase):
    def test_safe_thinking_log_summary_returns_empty_for_non_dict_payload(self):
        self.assertEqual(_safe_thinking_log_summary("not-a-dict"), "")

    def test_safe_thinking_log_summary_returns_empty_for_non_string_thinking_log(self):
        self.assertEqual(_safe_thinking_log_summary({"thinking_log": ["invalid"]}), "")

    def test_safe_thinking_log_summary_returns_empty_for_blank_thinking_log(self):
        self.assertEqual(_safe_thinking_log_summary({"thinking_log": "   \n\t  "}), "")

    def test_safe_thinking_log_summary_skips_blank_and_blocked_lines(self):
        summary = _safe_thinking_log_summary(
            {
                "thinking_log": (
                    "   \n"
                    "This is safe reasoning summary.\n"
                    "System prompt: do not expose\n"
                    "  \n"
                    "Another safe validation note."
                )
            }
        )

        self.assertEqual(
            summary,
            "This is safe reasoning summary.\nAnother safe validation note.",
        )

    def test_safe_thinking_log_summary_returns_empty_when_all_lines_blocked(self):
        summary = _safe_thinking_log_summary(
            {
                "thinking_log": (
                    "chain-of-thought: hidden\n"
                    "debug: internal trace\n"
                    "token: secret"
                )
            }
        )

        self.assertEqual(summary, "")

    def test_safe_thinking_log_summary_stops_after_max_chars(self):
        summary = _safe_thinking_log_summary(
            {
                "thinking_log": (
                    "A" * 1990
                    + "\n"
                    + "B" * 2000
                    + "\n"
                    + "This line should not be processed."
                )
            }
        )

        self.assertEqual(len(summary), 2000)
        self.assertTrue(summary.startswith("A" * 1990))
        self.assertIn("\n", summary)
        self.assertNotIn("This line should not be processed.", summary)

    def test_safe_thinking_log_summary_stops_when_limit_is_exactly_reached(self):
        summary = _safe_thinking_log_summary(
            {
                "thinking_log": (
                    "A" * 2000
                    + "\n"
                    + "This line should not be processed either."
                )
            }
        )

        self.assertEqual(len(summary), 2000)
        self.assertEqual(summary, "A" * 2000)

    def test_thinking_log_item_serializer_handles_non_dict_output_json(self):
        instance = SimpleNamespace(
            id=uuid4(),
            output_json="not-a-dict",
            status_processing="completed",
            created_at=timezone.now(),
        )

        serializer = ThinkingLogItemSerializer(instance)

        self.assertIsNone(serializer.data["session_id"])
        self.assertNotIn("request_id", serializer.data)
        self.assertEqual(serializer.data["thinking_log"], "")


class SendMessageSerializerTest(SimpleTestCase):
    def test_send_message_request_serializer_accepts_non_blank_message(self):
        serializer = SendMessageRequestSerializer(data={"message": "Hello"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["message"], "Hello")

    def test_send_message_request_serializer_rejects_whitespace_only_message(self):
        serializer = SendMessageRequestSerializer(data={"message": "   \n\t"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("message", serializer.errors)

    def test_thinking_log_item_serializer_omits_request_id_even_if_present_in_output_json(self):
        instance = SimpleNamespace(
            id=uuid4(),
            session_id=uuid4(),
            source_message_id=uuid4(),
            output_json={"request_id": "req-123"},
            thinking_log="Structured summary",
            status_processing="completed",
            created_at=timezone.now(),
        )

        serializer = ThinkingLogItemSerializer(instance)

        self.assertEqual(serializer.data["chat_id"], str(instance.source_message_id))
        self.assertNotIn("request_id", serializer.data)

    def test_thinking_log_item_serializer_does_not_classify_output_json_session_id_as_chat(self):
        instance = SimpleNamespace(
            id=uuid4(),
            output_json={"session_id": str(uuid4()), "request_id": "req-456"},
            thinking_log="Structured summary",
            status_processing="completed",
            created_at=timezone.now(),
        )

        serializer = ThinkingLogItemSerializer(instance)

        self.assertIsNone(serializer.data["session_id"])
        self.assertIsNone(serializer.data["chat_id"])
        self.assertNotIn("request_id", serializer.data)

    def test_thinking_log_item_serializer_returns_empty_reasoning_when_reasoning_steps_is_not_list(self):
        instance = SimpleNamespace(
            id=uuid4(),
            output_json={},
            thinking_log="Structured summary",
            reasoning={"reasoning_steps": "single-step-string"},
            status_processing="completed",
            created_at=timezone.now(),
        )

        serializer = ThinkingLogItemSerializer(instance)

        self.assertEqual(serializer.data["reasoning"], [])

    def test_thinking_log_item_serializer_returns_reasoning_steps_when_list(self):
        instance = SimpleNamespace(
            id=uuid4(),
            output_json={},
            thinking_log="Structured summary",
            reasoning={"reasoning_steps": ["Step one", "Step two"]},
            status_processing="completed",
            created_at=timezone.now(),
        )

        serializer = ThinkingLogItemSerializer(instance)

        self.assertEqual(serializer.data["reasoning"], ["Step one", "Step two"])
