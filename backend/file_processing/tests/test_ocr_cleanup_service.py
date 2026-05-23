from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from file_processing.services.ocr_cleanup_service import (
    OCRCleanupService,
    _case_preserving_replace,
    _flatten_terms,
    _is_preservable_token,
    _word_confidence,
)


class OCRCleanupServiceTest(SimpleTestCase):
    def test_cleanup_text_corrects_high_confidence_typos_and_preserves_low_confidence(self):
        spell_checker = Mock()
        spell_checker.known.return_value = False
        spell_checker.correction.side_effect = lambda word: {
            "teh": "the",
            "lncome": "income",
        }.get(word)

        service = OCRCleanupService(spell_checker=spell_checker)
        result = service.cleanup_text(
            text="teh revenue\nlncome remains",
            avg_confidence=90.0,
            word_details=[
                {"text": "teh", "confidence": 96.0, "block_num": 1, "par_num": 1, "line_num": 1, "left": 10},
                {"text": "revenue", "confidence": 94.0, "block_num": 1, "par_num": 1, "line_num": 1, "left": 20},
                {"text": "lncome", "confidence": 34.0, "block_num": 1, "par_num": 1, "line_num": 2, "left": 10},
                {"text": "remains", "confidence": 32.0, "block_num": 1, "par_num": 1, "line_num": 2, "left": 20},
            ],
            document_type="pdf",
        )

        self.assertEqual(result["text"], "the revenue\nlncome remains")
        self.assertIn("teh->the", result["corrections_applied"])
        self.assertEqual(result["ocr_metadata"]["confidence_level"], "medium")
        self.assertEqual(len(result["ocr_metadata"]["low_confidence_regions"]), 2)

    def test_summarize_page_metadata_aggregates_page_confidences(self):
        summary = OCRCleanupService.summarize_page_metadata(
            [
                {
                    "confidence_score": 90.0,
                    "corrections_applied": ["a->b"],
                    "low_confidence_regions": [{"text": "x", "confidence": 35.0}],
                },
                {
                    "confidence_score": 50.0,
                    "corrections_applied": [],
                    "low_confidence_regions": [],
                },
            ],
            document_type="image",
        )

        self.assertEqual(summary["document_type"], "image")
        self.assertEqual(summary["confidence_level"], "medium")
        self.assertEqual(summary["correction_count"], 1)

    def test_build_spell_checker_returns_none_when_dependency_missing(self):
        with patch("file_processing.services.ocr_cleanup_service.SpellChecker", None):
            self.assertIsNone(OCRCleanupService._build_spell_checker())

    def test_build_spell_checker_handles_initialization_failure(self):
        with patch(
            "file_processing.services.ocr_cleanup_service.SpellChecker",
        ) as mock_spellchecker:
            mock_spellchecker.side_effect = Exception("boom")
            self.assertIsNone(OCRCleanupService._build_spell_checker())

    def test_case_preserving_replace_and_preservable_token_helpers(self):
        self.assertEqual(_case_preserving_replace("ABC", "invoice"), "INVOICE")
        self.assertEqual(_case_preserving_replace("Abc", "invoice"), "Invoice")
        self.assertEqual(_case_preserving_replace("abc", "invoice"), "invoice")

        self.assertTrue(_is_preservable_token(""))
        self.assertTrue(_is_preservable_token("1,234.50"))
        self.assertTrue(_is_preservable_token("ABC123"))
        self.assertTrue(_is_preservable_token("SKU"))
        self.assertTrue(_is_preservable_token("A_B"))
        self.assertFalse(_is_preservable_token("invoice"))

    def test_word_confidence_and_spellchecker_known_branch(self):
        spell_checker = Mock()
        spell_checker.known.return_value = True
        service = OCRCleanupService(spell_checker=spell_checker)

        self.assertEqual(service._spellchecker_candidate("invoice"), "invoice")
        self.assertEqual(_word_confidence({"confidence": "bad"}), 0.0)
        self.assertEqual(_word_confidence({"conf": 77.5}), 77.5)

    def test_flatten_terms_and_candidate_selection(self):
        terms = OCRCleanupService._extract_candidate_terms({"a": ["Alpha", {"b": "Beta_1"}]})

        self.assertIn("alpha", terms)
        self.assertIn("beta_1", terms)
        self.assertEqual(_flatten_terms("Alpha Beta Gamma"), {"alpha", "beta", "gamma"})
        self.assertEqual(_flatten_terms(("One", "Two")), {"one", "two"})

    def test_spellchecker_candidate_and_fallback_and_corrections(self):
        spell_checker = Mock()
        spell_checker.known.return_value = False
        spell_checker.correction.return_value = "invoice"
        service = OCRCleanupService(spell_checker=spell_checker)

        self.assertEqual(service._spellchecker_candidate("inv0ice"), "invoice")
        self.assertEqual(service._fallback_candidate("invoic", {"invoice", "total"}), "invoice")
        spell_checker.correction.return_value = "invoice"
        self.assertEqual(service._correct_token("invocie", {"invoice"}), ("invoice", "invocie->invoice"))
        self.assertEqual(service._correct_token("", {"invoice"}), ("", None))
        self.assertEqual(service._correct_token("123", {"invoice"}), ("123", None))
        self.assertEqual(service._correct_token("A_B", {"invoice"}), ("A_B", None))
        self.assertEqual(service._correct_token("teh!", {"invoice"}), ("teh!", None))

    def test_line_and_word_cleanup_branches(self):
        service = OCRCleanupService(spell_checker=Mock())
        self.assertEqual(service._clean_line("teh total", 40.0, {"total"}), ("teh total", []))
        spell_checker = Mock()
        spell_checker.known.return_value = False
        spell_checker.correction.return_value = "the"
        service_with_corrections = OCRCleanupService(spell_checker=spell_checker)
        self.assertEqual(
            service_with_corrections._clean_line("teh value", 90.0, {"value"}),
            ("the value", ["teh->the"]),
        )
        self.assertEqual(service._clean_word("typo", 40.0, {"typo"}), ("typo", None))

    def test_cleanup_without_word_details_and_region_building(self):
        service = OCRCleanupService(spell_checker=Mock())

        result = service.cleanup_text(
            text="line one\nline two",
            avg_confidence=55.0,
            word_details=None,
            document_type="pdf",
        )

        self.assertEqual(result["ocr_metadata"]["processing_method"], "tesseract_line_cleanup")
        self.assertEqual(len(result["regions"]), 2)
        self.assertEqual(len(result["ocr_metadata"]["low_confidence_regions"]), 2)

    def test_cleanup_with_word_details_skips_blank_words_and_non_empty_branch(self):
        spell_checker = Mock()
        spell_checker.known.return_value = False
        spell_checker.correction.return_value = "the"
        service = OCRCleanupService(spell_checker=spell_checker)

        result = service.cleanup_text(
            text="teh",
            avg_confidence=90.0,
            word_details=[
                {"text": "", "confidence": 91.0, "block_num": 1, "par_num": 1, "line_num": 1},
                {"text": "teh", "confidence": 91.0, "block_num": 1, "par_num": 1, "line_num": 1},
            ],
            document_type="pdf",
        )

        self.assertEqual(result["text"], "the")
        self.assertIn("teh->the", result["corrections_applied"])

    def test_cleanup_with_word_details_skips_empty_group_and_blank_fallback(self):
        class WeirdStr(str):
            def splitlines(self, keepends=False):
                return []

            def strip(self, chars=None):
                return "x"

        service = OCRCleanupService(spell_checker=Mock())
        result = service.cleanup_text(
            text=WeirdStr("x"),
            avg_confidence=12.0,
            word_details=[
                {"text": "", "confidence": 30.0, "block_num": 1, "par_num": 1, "line_num": 1},
                {"text": "real", "confidence": 91.0, "block_num": 1, "par_num": 1, "line_num": 2},
            ],
            document_type="pdf",
        )

        self.assertEqual(result["text"], "real")
        self.assertEqual(result["ocr_metadata"]["confidence_level"], "high")

    def test_cleanup_without_word_details_uses_text_strip_fallback_when_splitlines_empty(self):
        class WeirdStr(str):
            def splitlines(self, keepends=False):
                return []

            def strip(self, chars=None):
                return "fallback text"

        service = OCRCleanupService(spell_checker=Mock())
        result = service.cleanup_text(
            text=WeirdStr("fallback text"),
            avg_confidence=12.0,
            word_details=None,
            document_type="pdf",
        )

        self.assertEqual(result["text"], "fallback text")
        self.assertEqual(result["ocr_metadata"]["processing_method"], "tesseract_line_cleanup")

    def test_region_helpers_cover_empty_inputs(self):
        self.assertEqual(OCRCleanupService._build_regions([]), [])
        self.assertEqual(OCRCleanupService._build_low_confidence_regions([]), [])
        self.assertEqual(OCRCleanupService._aggregate_confidence([], 12.5), 12.5)

    def test_summarize_page_metadata_empty_input(self):
        summary = OCRCleanupService.summarize_page_metadata([], document_type="pdf")

        self.assertEqual(summary["confidence_score"], 0.0)
        self.assertEqual(summary["correction_count"], 0)

    def test_summarize_page_metadata_skips_non_dict_pages(self):
        summary = OCRCleanupService.summarize_page_metadata(
            [
                {"confidence_score": 80.0, "corrections_applied": ["a->b"], "low_confidence_regions": []},
                "not-a-dict",
            ],
            document_type="pdf",
        )

        self.assertEqual(summary["confidence_score"], 80.0)
        self.assertEqual(summary["correction_count"], 1)

    def test_remove_space_before_punct_handles_empty_and_skips_space_before_punctuation(self):
        self.assertEqual(OCRCleanupService._remove_space_before_punct(""), "")
        self.assertEqual(OCRCleanupService._remove_space_before_punct("alpha   , beta"), "alpha, beta")

    def test_spellchecker_candidate_returns_none_when_spellchecker_unavailable(self):
        service = OCRCleanupService(spell_checker=None)
        service.spell_checker = None

        self.assertIsNone(service._spellchecker_candidate("invoice"))

    def test_flatten_terms_covers_empty_and_non_normalized_chunks(self):
        with patch("file_processing.services.ocr_cleanup_service.re.findall", return_value=["   ", "Alpha"]):
            terms = _flatten_terms("ignored")

        self.assertEqual(terms, {"alpha"})
        self.assertEqual(_flatten_terms([]), set())
        self.assertEqual(_flatten_terms(123), set())
