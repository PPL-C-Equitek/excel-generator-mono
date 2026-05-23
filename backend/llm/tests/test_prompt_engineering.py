from django.test import SimpleTestCase

from llm.prompts.extraction import build_extraction_prompt
from llm.prompts.base import sanitize_user_input
from llm.prompts.schemas import (
    EXTRACTION_OUTPUT_SCHEMA_KEYS,
    _to_json_context,
    build_conversion_reasoning_prompt,
)


class ExtractionPromptBuilderTest(SimpleTestCase):
    def test_positive_prompt_includes_strict_json_and_required_schema(self):
        prompt = build_extraction_prompt()

        self.assertIn("ONLY valid JSON", prompt)
        self.assertIn('"document_info"', prompt)
        self.assertIn('"summary"', prompt)
        self.assertIn('"content_data"', prompt)
        self.assertNotIn('"reasoning_steps"', prompt)
        self.assertNotIn('"final_answer"', prompt)
        self.assertIn("no top-level keys besides: document_info, summary, content_data", prompt)

    def test_negative_ambiguous_input_still_enforces_schema_no_free_form(self):
        prompt = build_extraction_prompt()

        self.assertIn("If extraction is ambiguous or insufficient", prompt)
        self.assertIn("keep the same required output contract", prompt)
        self.assertIn("do not invent values", prompt)
        self.assertIn("no markdown", prompt)
        self.assertIn("no code fences", prompt)
        self.assertIn("no extra explanation outside JSON", prompt)

    def test_edge_case_prompt_keeps_schema_and_inference_guidance(self):
        prompt = build_extraction_prompt()

        self.assertIn("infer likely headers", prompt)
        self.assertIn("normalize values", prompt)
        self.assertIn("preserve row consistency", prompt)
        self.assertIn('"unit"', prompt)
        self.assertIn('"item"', prompt)
        self.assertIn('"num_type"', prompt)
        self.assertIn('"status_type"', prompt)
        self.assertIn('"value"', prompt)
        self.assertIn("Never use translated or alternative names", prompt)
        for required_key in EXTRACTION_OUTPUT_SCHEMA_KEYS:
            self.assertIn(f'"{required_key}"', prompt)

    def test_modularity_schema_rules_are_isolated_from_task_instructions(self):
        prompt = build_extraction_prompt()

        self.assertIn("## TASK", prompt)
        self.assertIn("## OUTPUT_FORMAT", prompt)
        self.assertLess(prompt.find("## TASK"), prompt.find("## OUTPUT_FORMAT"))
        self.assertEqual(
            EXTRACTION_OUTPUT_SCHEMA_KEYS,
            ["document_info", "summary", "content_data"],
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

    def test_build_extraction_prompt_includes_refinement_section_when_provided(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item]",
            refinement_instruction="Fix summary.total_items mismatch.",
        )

        self.assertIn("## SCHEMA_HINT", prompt)
        self.assertIn("## REFINEMENT", prompt)
        self.assertIn("Fix summary.total_items mismatch.", prompt)

    def test_build_extraction_prompt_ignores_blank_refinement_instruction(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item]",
            refinement_instruction="   ",
        )

        self.assertIn("## SCHEMA_HINT", prompt)
        self.assertNotIn("## REFINEMENT", prompt)

    def test_build_extraction_prompt_includes_refinement_without_schema_hint(self):
        prompt = build_extraction_prompt(
            schema_hint="   ",
            refinement_instruction="Repair content_data row mapping.",
        )

        self.assertNotIn("## SCHEMA_HINT", prompt)
        self.assertIn("## REFINEMENT", prompt)
        self.assertIn("Repair content_data row mapping.", prompt)

    def test_build_extraction_prompt_includes_ocr_context_when_provided(self):
        prompt = build_extraction_prompt(
            ocr_context={
                "confidence_score": 58.0,
                "confidence_level": "low",
                "document_type": "image",
                "processing_method": "tesseract_multi_psm_layout_aware",
                "low_confidence_regions": [{"text": "lncome", "confidence": 42.0}],
                "corrections_applied": ["lncome->income"],
            },
        )

        self.assertIn("## OCR_QUALITY_CONTEXT", prompt)
        self.assertIn("Document Type: image", prompt)
        self.assertIn("OCR Confidence: 58.0% (low)", prompt)
        self.assertIn("Low-Confidence Regions (first 5):", prompt)
        self.assertIn("lncome", prompt)

    def test_build_extraction_prompt_supports_string_ocr_context(self):
        prompt = build_extraction_prompt(ocr_context="  OCR metadata as raw text  ")

        self.assertIn("## OCR_QUALITY_CONTEXT", prompt)
        self.assertIn("OCR metadata as raw text", prompt)

    def test_build_extraction_prompt_ignores_blank_ocr_context(self):
        prompt = build_extraction_prompt(ocr_context="   ")

        self.assertNotIn("## OCR_QUALITY_CONTEXT", prompt)

    def test_build_extraction_prompt_supports_schema_chat_and_refinement_together(self):
        prompt = build_extraction_prompt(
            schema_hint="headers: [item]",
            chat_context="USER: Gunakan Bahasa Indonesia",
            refinement_instruction="Fix summary.total_items mismatch.",
        )

        self.assertIn("## SCHEMA_HINT", prompt)
        self.assertIn("## CHAT_CONTEXT", prompt)
        self.assertIn("## REFINEMENT", prompt)
        self.assertLess(prompt.find("## SCHEMA_HINT"), prompt.find("## CHAT_CONTEXT"))
        self.assertLess(prompt.find("## CHAT_CONTEXT"), prompt.find("## REFINEMENT"))

    def test_to_json_context_truncates_when_output_too_long(self):
        result = _to_json_context({"value": "x" * 30}, max_chars=10)

        self.assertTrue(result.endswith("... [TRUNCATED]"))

    def test_to_json_context_falls_back_to_string_for_non_serializable_value(self):
        class NonSerializable:
            def __str__(self):
                return "non-serializable-context"

        result = _to_json_context(NonSerializable(), max_chars=100)

        self.assertEqual(result, "non-serializable-context")

    def test_build_conversion_reasoning_prompt_includes_context_sections(self):
        prompt = build_conversion_reasoning_prompt(
            input_json={"headers": ["A"]},
            output_json={"rows": [["1"]]},
            file_name="sample.xlsx",
            document_type="xlsx",
        )

        self.assertIn("CONTEXT:", prompt)
        self.assertIn("- file_name: sample.xlsx", prompt)
        self.assertIn("- document_type: xlsx", prompt)
        self.assertIn("INPUT_JSON:", prompt)
        self.assertIn("OUTPUT_JSON:", prompt)

    def test_build_conversion_reasoning_prompt_compacts_upload_wrapper_and_hides_raw_rows(self):
        prompt = build_conversion_reasoning_prompt(
            input_json={
                "status": "success",
                "message": "File uploaded successfully",
                "filename": "invoice.pdf",
                "format": "pdf",
                "size": 123,
                "extracted": {
                    "Sheet1": [
                        ["header_1", "header_2"],
                        ["RAW_INPUT_SECRET_VALUE", "1000"],
                    ]
                },
                "user_prompt": "Only keep paid rows",
            },
            output_json={
                "document_info": {"source_type": "PDF", "filename": "invoice.pdf"},
                "summary": {"total_tables": 1, "total_rows": 1, "total_columns": 2},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["status", "amount"],
                        "rows": [{"status": "PAID", "amount": "RAW_OUTPUT_SECRET_VALUE"}],
                    }
                ],
            },
            file_name="invoice.pdf",
            document_type="pdf",
        )

        self.assertIn("upload_wrapper", prompt)
        self.assertIn("tabular_output", prompt)
        self.assertIn("table_count", prompt)
        self.assertIn("header_count", prompt)
        self.assertNotIn("RAW_INPUT_SECRET_VALUE", prompt)
        self.assertNotIn("RAW_OUTPUT_SECRET_VALUE", prompt)

    def test_build_conversion_reasoning_prompt_compacts_large_nested_payload(self):
        huge_value = "X" * 5000
        prompt = build_conversion_reasoning_prompt(
            input_json={
                "extracted": {
                    "Sheet1": [["col1"], [huge_value]],
                }
            },
            output_json={"content_data": [{"table_name": "Sheet1", "headers": ["col1"], "rows": [{"col1": huge_value}]}]},
        )

        self.assertLess(len(prompt), 10000)
