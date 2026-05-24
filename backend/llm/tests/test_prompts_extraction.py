from django.test import SimpleTestCase

from llm.prompts import extraction as extraction_mod


class PromptsExtractionTest(SimpleTestCase):
    def test_build_schema_hint_section_handles_blank_and_nonblank(self):
        self.assertIsNone(extraction_mod._build_schema_hint_section(None))
        self.assertIsNone(extraction_mod._build_schema_hint_section("   "))
        section = extraction_mod._build_schema_hint_section("  id,name,total  ")
        self.assertIn("SCHEMA_HINT", section)
        self.assertIn("id,name,total", section)

    def test_build_section_context_section_with_string_and_dict_variants(self):
        # string variant
        result = extraction_mod._build_section_context_section("  Finance and Sales  ")
        self.assertIn("SECTION_CONTEXT", result)
        self.assertIn("Finance and Sales", result)

        # dict variant with full fields
        ctx = {
            "source_type": "extracted_map",
            "section_count": 3,
            "section_labels": [" A ", "B", "  ", "C"],
            "section_markers": [" marker1 ", "marker2"],
            "instruction": "  Use markers conservatively.  ",
        }
        result2 = extraction_mod._build_section_context_section(ctx)
        self.assertIn("Source: extracted_map", result2)
        self.assertIn("Likely Sections: 3", result2)
        # labels should be normalized and empty entries dropped
        self.assertIn("- A", result2)
        self.assertIn("- B", result2)
        self.assertIn("- C", result2)
        self.assertIn("Section Markers:", result2)
        self.assertIn("Use markers conservatively.", result2)

    def test_build_ocr_context_section_with_string_and_nested_dict(self):
        self.assertIsNone(extraction_mod._build_ocr_context_section(None))
        s = extraction_mod._build_ocr_context_section("  low confidence on page  ")
        self.assertIn("OCR_QUALITY_CONTEXT", s)
        self.assertIn("low confidence on page", s)

        d = {
            "confidence_score": 42.0,
            "confidence_level": "medium",
            "document_type": "pdf",
            "processing_method": "tesseract",
            "corrections_applied": ["a"],
            "low_confidence_regions": [
                {"text": "unclear text", "confidence": 12},
            ],
        }
        out = extraction_mod._build_ocr_context_section(d)
        self.assertIn("Document Type: pdf", out)
        self.assertIn("Processing Method: tesseract", out)
        self.assertIn("unclear text", out)

    def test_build_extraction_prompt_assembles_sections(self):
        prompt = extraction_mod.build_extraction_prompt(
            schema_hint=" id,name ",
            section_context={"source_type": "page_content", "section_labels": ["X"]},
            refinement_instruction=" fix headers ",
            chat_context=" user asked to preserve currency ",
            ocr_context={"confidence_score": 55},
        )

        self.assertIn("SCHEMA_HINT", prompt)
        self.assertIn("SECTION_CONTEXT", prompt)
        self.assertIn("OCR_QUALITY_CONTEXT", prompt)
        self.assertIn("CHAT_CONTEXT", prompt)
        self.assertIn("REFINEMENT", prompt)

    def test_append_section_context_values_skips_blank_entries(self):
        lines = []

        extraction_mod._append_section_context_values(
            lines,
            "Labels:",
            [" A ", "   ", "", "B"],
        )

        self.assertEqual(
            lines,
            [
                "Labels:",
                "- A",
                "- B",
            ],
        )

    def test_normalize_section_context_values_handles_invalid_types(self):
        self.assertEqual(
            extraction_mod._normalize_section_context_values(
                [" A ", None, 123, " ", "B"]
            ),
            ["A", "B"],
        )

        self.assertEqual(
            extraction_mod._normalize_section_context_values("not-a-list"),
            [],
        )

    def test_append_section_context_values_handles_empty_and_non_empty_values(self):
        lines = []

        extraction_mod._append_section_context_values(
            lines,
            "Labels:",
            ["  Finance  ", "   ", ""],
        )

        self.assertEqual(
            lines,
            [
                "Labels:",
                "- Finance",
            ],
        )

    def test_build_section_context_section_skips_blank_source_type(self):
        result = extraction_mod._build_section_context_section(
            {
                "source_type": "   ",
                "section_count": 2,
                "section_labels": ["Finance", "Sales"],
            }
        )

        self.assertIn("Likely Sections: 2", result)
        self.assertNotIn("Source:", result)
