from django.test import SimpleTestCase
from unittest.mock import Mock

from file_processing.extractors.ocr.ocr_strategy import (
    OCRCleanupOrchestrator,
    ImageOCRStrategy,
    OCRStrategyFactory,
    PDFOCRStrategy,
    ScannedExcelOCRStrategy,
)


class OCRStrategyFactoryTest(SimpleTestCase):
    def test_get_strategy_returns_document_specific_strategy(self):
        self.assertIsInstance(OCRStrategyFactory.get_strategy("pdf"), PDFOCRStrategy)
        self.assertIsInstance(OCRStrategyFactory.get_strategy("image"), ImageOCRStrategy)
        self.assertIsInstance(
            OCRStrategyFactory.get_strategy("scanned_excel"),
            ScannedExcelOCRStrategy,
        )

    def test_strategy_cleanup_uses_document_type(self):
        cleanup_service = Mock()
        cleanup_service.cleanup_text.return_value = {"ocr_metadata": {"document_type": "pdf"}}

        strategy = PDFOCRStrategy(cleanup_service=cleanup_service)
        result = strategy.cleanup_text(text="sample", word_details=[], avg_confidence=91.0)

        cleanup_service.cleanup_text.assert_called_once_with(
            text="sample",
            avg_confidence=91.0,
            word_details=[],
            schema_definitions=None,
            document_type="pdf",
        )
        self.assertEqual(result["ocr_metadata"]["document_type"], "pdf")

    def test_orchestrator_returns_copy_of_ocr_metadata(self):
        cleanup_result = {"ocr_metadata": {"confidence_score": 88.0, "document_type": "image"}}

        context = OCRCleanupOrchestrator.to_llm_context(cleanup_result)

        self.assertEqual(context, cleanup_result["ocr_metadata"])
        self.assertIsNot(context, cleanup_result["ocr_metadata"])

    def test_get_strategy_defaults_for_unknown_document_type(self):
        strategy = OCRStrategyFactory.get_strategy("unknown-type")

        self.assertEqual(strategy.document_type, "unknown")
