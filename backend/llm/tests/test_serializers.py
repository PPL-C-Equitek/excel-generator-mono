from django.test import SimpleTestCase

from llm.serializers import (
    LlmGenerateRequestSerializer,
    LlmGenerateResponseSerializer,
    LlmReasoningRequestSerializer,
    LlmReasoningResponseSerializer,
)


class LlmGenerateSerializerTest(SimpleTestCase):
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