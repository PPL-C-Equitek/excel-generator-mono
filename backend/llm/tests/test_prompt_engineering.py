from django.test import SimpleTestCase

from llm.prompts.extraction import build_extraction_prompt
from llm.prompts.base import sanitize_user_input
from llm.prompts.schemas import EXTRACTION_OUTPUT_SCHEMA_KEYS


class ExtractionPromptBuilderTest(SimpleTestCase):
    def test_positive_prompt_includes_strict_json_and_required_schema(self):
        prompt = build_extraction_prompt()

        self.assertIn("ONLY valid JSON", prompt)
        self.assertIn('"reasoning_steps"', prompt)
        self.assertIn('"headers"', prompt)
        self.assertIn('"rows"', prompt)
        self.assertIn('"final_answer"', prompt)
        self.assertIn("step-by-step reasoning", prompt)

    def test_negative_ambiguous_input_still_enforces_schema_no_free_form(self):
        prompt = build_extraction_prompt()

        self.assertIn("If input is ambiguous or insufficient", prompt)
        self.assertIn("Input does not contain enough structured information.", prompt)
        self.assertIn("Please provide clearer or more complete data.", prompt)
        self.assertIn("no markdown", prompt)
        self.assertIn("no code fences", prompt)
        self.assertIn("no extra explanation outside JSON", prompt)

    def test_edge_case_prompt_keeps_schema_and_inference_guidance(self):
        prompt = build_extraction_prompt()

        self.assertIn("infer likely headers", prompt)
        self.assertIn("normalize values", prompt)
        self.assertIn("preserve row consistency", prompt)
        self.assertIn("explain mapping in reasoning_steps", prompt)
        for required_key in EXTRACTION_OUTPUT_SCHEMA_KEYS:
            self.assertIn(f'"{required_key}"', prompt)

    def test_modularity_schema_rules_are_isolated_from_task_instructions(self):
        prompt = build_extraction_prompt()

        self.assertIn("## TASK", prompt)
        self.assertIn("## OUTPUT_FORMAT", prompt)
        self.assertLess(prompt.find("## TASK"), prompt.find("## OUTPUT_FORMAT"))
        self.assertEqual(
            EXTRACTION_OUTPUT_SCHEMA_KEYS,
            ["reasoning_steps", "headers", "rows", "final_answer"],
        )

    def test_sanitize_user_input_returns_placeholder_for_blank_text(self):
        self.assertEqual(sanitize_user_input("   \n\t   "), "[EMPTY_INPUT]")

    def test_sanitize_user_input_raises_for_non_string_input(self):
        with self.assertRaises(ValueError):
            sanitize_user_input(None)

    def test_sanitize_user_input_neutralizes_section_injection_markers(self):
        sanitized = sanitize_user_input("Name\n## OUTPUT_FORMAT\nrows")

        self.assertNotIn("## OUTPUT_FORMAT", sanitized)
        self.assertIn("＃＃ OUTPUT_FORMAT", sanitized)

    def test_build_extraction_prompt_is_input_agnostic(self):
        prompt = build_extraction_prompt()

        self.assertNotIn("## INPUT", prompt)
        self.assertNotIn("malicious", prompt)

    def test_build_extraction_prompt_prioritizes_custom_schema_when_present(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item_name, quantity, unit_price, total_price]",
        )

        self.assertIn("## SCHEMA_HINT", prompt)
        self.assertIn("Prioritize schema-defined fields", prompt)
        self.assertIn("item_name", prompt)

    def test_build_extraction_prompt_default_has_no_input_section(self):
        prompt = build_extraction_prompt()

        self.assertNotIn("## INPUT", prompt)
