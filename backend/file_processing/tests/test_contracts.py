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

    def test_warnings_is_immutable_tuple(self):
        """Verify warnings cannot be mutated externally after construction."""
        warnings_list = ["warning1", "warning2"]
        result = ExtractionResult.ok({"data": []}, warnings=warnings_list)

        # Verify warnings is a tuple
        self.assertIsInstance(result.warnings, tuple)
        self.assertEqual(result.warnings, ("warning1", "warning2"))

        # Mutate the original list — should not affect frozen result
        warnings_list.append("warning3")
        self.assertEqual(result.warnings, ("warning1", "warning2"))
        self.assertEqual(len(result.warnings), 2)

    def test_frozen_result_rejects_mutations(self):
        """Verify the dataclass is truly frozen."""
        result = ExtractionResult.ok({"data": []})

        # Attempting to mutate any field should raise FrozenInstanceError
        with self.assertRaises(Exception):  # FrozenInstanceError
            result.warnings = ("new",)


class TestUploadPipelineExceptions(SimpleTestCase):
    def test_validation_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadValidationError, UploadPipelineError))

    def test_extraction_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadExtractionError, UploadPipelineError))

    def test_storage_error_is_pipeline_error(self):
        self.assertTrue(issubclass(UploadStorageError, UploadPipelineError))
