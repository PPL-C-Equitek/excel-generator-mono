from django.test import SimpleTestCase
from unittest.mock import Mock

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
