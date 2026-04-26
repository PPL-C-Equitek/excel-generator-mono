from django.test import SimpleTestCase
from types import SimpleNamespace
from uuid import uuid4

from django.utils import timezone

from llm.serializers import (
    LlmGenerateRequestSerializer,
    LlmGenerateResponseSerializer,
    LlmReasoningRequestSerializer,
    LlmReasoningResponseSerializer,
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
        serializer = LlmGenerateResponseSerializer(
            data={
                "output_json": {"sheet": "Sheet1"},
                "session_id": str(uuid4()),
                "output_id": str(uuid4()),
                "reasoning": None,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generate_request_serializer_accepts_include_reasoning(self):
        serializer = LlmGenerateRequestSerializer(
            data={"input_json": {"sheet": "Sheet1"}, "include_reasoning": False}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["include_reasoning"])

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
        self.assertIsNone(serializer.data["request_id"])
        self.assertEqual(serializer.data["thinking_log"], "")
