from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from file_processing.services.ocr_cleanup_service import OCRCleanupService


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

    def test_flatten_terms_and_candidate_selection(self):
        terms = OCRCleanupService._extract_candidate_terms({"a": ["Alpha", {"b": "Beta_1"}]})

        self.assertIn("alpha", terms)
        self.assertIn("beta_1", terms)

    def test_spellchecker_candidate_and_fallback_and_corrections(self):
        spell_checker = Mock()
        spell_checker.known.return_value = False
        spell_checker.correction.return_value = "invoice"
        service = OCRCleanupService(spell_checker=spell_checker)

        self.assertEqual(service._spellchecker_candidate("inv0ice"), "invoice")
        self.assertEqual(service._fallback_candidate("invoic", {"invoice", "total"}), "invoice")
        spell_checker.correction.return_value = "invoice"
        self.assertEqual(service._correct_token("invocie", {"invoice"}), ("invoice", "invocie->invoice"))
        self.assertEqual(service._correct_token("123", {"invoice"}), ("123", None))

    def test_line_and_word_cleanup_branches(self):
        service = OCRCleanupService(spell_checker=Mock())
        self.assertEqual(service._clean_line("teh total", 40.0, {"total"}), ("teh total", []))
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

    def test_region_helpers_cover_empty_inputs(self):
        self.assertEqual(OCRCleanupService._build_regions([]), [])
        self.assertEqual(OCRCleanupService._build_low_confidence_regions([]), [])
        self.assertEqual(OCRCleanupService._aggregate_confidence([], 12.5), 12.5)

    def test_summarize_page_metadata_empty_input(self):
        summary = OCRCleanupService.summarize_page_metadata([], document_type="pdf")

        self.assertEqual(summary["confidence_score"], 0.0)
        self.assertEqual(summary["correction_count"], 0)
