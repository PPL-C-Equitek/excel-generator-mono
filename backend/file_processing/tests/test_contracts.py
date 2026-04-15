from django.test import SimpleTestCase

from file_processing.services.contracts import ValidationResult, ExtractionResult
from file_processing.services.exceptions import (
    UploadPipelineError,
    UploadValidationError,
    UploadExtractionError,
    UploadStorageError,
)


class TestValidationResult(SimpleTestCase):
    def test_ok_to_legacy_tuple(self):
        result = ValidationResult.ok()

        self.assertEqual(result.to_legacy_tuple(), (True, None))

    def test_fail_to_legacy_tuple(self):
        result = ValidationResult.fail("invalid mime", code="mime_mismatch")

        self.assertEqual(result.to_legacy_tuple(), (False, "invalid mime"))
        self.assertEqual(result.code, "mime_mismatch")


class TestExtractionResult(SimpleTestCase):
    def test_ok_to_legacy_tuple(self):
        payload = {"content": [{"page": 1, "text": ["hello"]}]}
        result = ExtractionResult.ok(payload)

        self.assertEqual(result.to_legacy_tuple(), (True, None, payload))

    def test_fail_to_legacy_tuple(self):
        result = ExtractionResult.fail("ocr failed")

        self.assertEqual(result.to_legacy_tuple(), (False, "ocr failed", None))

    def test_from_legacy_tuple(self):
        payload = {"content": []}
        result = ExtractionResult.from_legacy_tuple((True, None, payload))

        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertEqual(result.extracted_data, payload)


class TestUploadPipelineExceptions(SimpleTestCase):
    def test_validation_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadValidationError, UploadPipelineError))

    def test_extraction_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadExtractionError, UploadPipelineError))

    def test_storage_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadStorageError, UploadPipelineError))
