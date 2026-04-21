import unittest
from hypothesis import given, settings, strategies as st
from django.core.files.uploadedfile import SimpleUploadedFile
from file_processing.services import word_validation_service


class TestWordValidationHypothesis(unittest.TestCase):
    @given(page_count=st.integers(min_value=0, max_value=500))
    @settings(max_examples=150)
    def test_check_word_page_count_property(self, page_count):
        is_valid, error = word_validation_service.check_word_page_count(page_count)
        if page_count > word_validation_service.MAX_WORD_PAGES:
            self.assertFalse(is_valid)
            self.assertIn("maximum allowed page count", error)
        else:
            self.assertTrue(is_valid)
            self.assertIsNone(error)

    @given(n_breaks=st.integers(min_value=0, max_value=300))
    @settings(max_examples=120)
    def test_estimate_doc_page_count_monotonic_on_formfeed(self, n_breaks):
        payload = b"WordDocument" + (b"A\x0c" * n_breaks)
        count = word_validation_service.estimate_doc_page_count(payload)

        if n_breaks == 0:
            self.assertEqual(count, 0)

        else:
            self.assertGreaterEqual(count, n_breaks + 1)

    @given(n_breaks=st.integers(min_value=0, max_value=150))
    @settings(max_examples=80)
    def test_validate_word_doc_limit_property(self, n_breaks):
        payload = (
            word_validation_service.OLE_SIGNATURE
            + b"WordDocument"
            + (b"P\x0c" * n_breaks)
        )
        f = SimpleUploadedFile("x.doc", payload, content_type="application/msword")
        is_valid, error = word_validation_service.validate_word(f, ".doc")

        estimated_pages = n_breaks + 1 if n_breaks > 0 else 0
        if estimated_pages > word_validation_service.MAX_WORD_PAGES:
            self.assertFalse(is_valid)
            self.assertIn("maximum allowed page count", error)
        else:
            self.assertTrue(is_valid)
