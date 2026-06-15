import unittest

from file_processing.services.file_validation_strategy import (
    FileValidator,
    UnsupportedExtensionValidationStrategy,
    ImageValidationStrategy,
    FileSizeValidationStrategy,
    MimeTypeValidationStrategy,
    ExcelSheetValidationStrategy,
    WordValidationStrategy,
)


class DummyUploadedFile:
    def __init__(self, name, size=1):
        self.name = name
        self.size = size


class TestFileValidationStrategy(unittest.TestCase):
    def _validator(
        self,
        image_validator,
        mime_validator,
        excel_validator,
        word_validator,
        max_file_size=100,
    ):
        return FileValidator(
            strategies=[
                UnsupportedExtensionValidationStrategy({
                    ".pdf",
                    ".xls",
                    ".xlsx",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".doc",
                    ".docx",
                    ".txt",
                    ".csv",
                }),
                ImageValidationStrategy({".png", ".jpg", ".jpeg"}, image_validator),
                FileSizeValidationStrategy(max_file_size, "too large"),
                MimeTypeValidationStrategy(mime_validator),
                ExcelSheetValidationStrategy({".xls", ".xlsx"}, excel_validator),
                WordValidationStrategy({".doc", ".docx"}, word_validator),
            ]
        )

    def test_unsupported_extension_returns_error(self):
        validator = self._validator(
            image_validator=lambda _f: (True, None),
            mime_validator=lambda _f, _ext: (True, None),
            excel_validator=lambda _f, _ext: (True, None),
            word_validator=lambda _f, _ext: (True, None),
        )
        is_valid, error = validator.validate(DummyUploadedFile("malware.exe"))

        self.assertFalse(is_valid)
        self.assertIn("Unsupported file type", error)

    def test_image_short_circuits_other_checks(self):
        calls = {"mime": 0, "excel": 0, "word": 0}

        def mime_validator(_f, _ext):
            calls["mime"] += 1
            return True, None

        def excel_validator(_f, _ext):
            calls["excel"] += 1
            return True, None

        def word_validator(_f, _ext):
            calls["word"] += 1
            return True, None

        validator = self._validator(
            image_validator=lambda _f: (True, None),
            mime_validator=mime_validator,
            excel_validator=excel_validator,
            word_validator=word_validator,
        )
        is_valid, error = validator.validate(DummyUploadedFile("image.png"))

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(calls["mime"], 0)
        self.assertEqual(calls["excel"], 0)
        self.assertEqual(calls["word"], 0)

    def test_non_image_chain_runs_all_relevant_validators(self):
        calls = {"mime": 0, "excel": 0, "word": 0}

        def mime_validator(_f, _ext):
            calls["mime"] += 1
            return True, None

        def excel_validator(_f, _ext):
            calls["excel"] += 1
            return True, None

        def word_validator(_f, _ext):
            calls["word"] += 1
            return True, None

        validator = self._validator(
            image_validator=lambda _f: (True, None),
            mime_validator=mime_validator,
            excel_validator=excel_validator,
            word_validator=word_validator,
        )
        is_valid, error = validator.validate(DummyUploadedFile("book.xlsx"))

        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(calls["mime"], 1)
        self.assertEqual(calls["excel"], 1)
        self.assertEqual(calls["word"], 0)

    def test_file_size_validation_blocks_when_too_large(self):
        validator = self._validator(
            image_validator=lambda _f: (True, None),
            mime_validator=lambda _f, _ext: (True, None),
            excel_validator=lambda _f, _ext: (True, None),
            word_validator=lambda _f, _ext: (True, None),
            max_file_size=10,
        )
        is_valid, error = validator.validate(DummyUploadedFile("doc.txt", size=20))

        self.assertFalse(is_valid)
        self.assertEqual(error, "too large")

    def test_word_validation_error_propagates(self):
        validator = self._validator(
            image_validator=lambda _f: (True, None),
            mime_validator=lambda _f, _ext: (True, None),
            excel_validator=lambda _f, _ext: (True, None),
            word_validator=lambda _f, _ext: (False, "word invalid"),
        )
        is_valid, error = validator.validate(DummyUploadedFile("proposal.docx"))

        self.assertFalse(is_valid)
        self.assertEqual(error, "word invalid")
