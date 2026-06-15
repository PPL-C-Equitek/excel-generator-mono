import os
from abc import ABC, abstractmethod


class BaseFileValidationStrategy(ABC):
    @abstractmethod
    def apply(self, uploaded_file, ext):
        """
        Return None to continue validation chain.
        Return (is_valid, error) to stop the chain.
        """


class UnsupportedExtensionValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, allowed_extensions):
        self.allowed_extensions = allowed_extensions

    def apply(self, uploaded_file, ext):
        if ext not in self.allowed_extensions:
            return (
                False,
                "Unsupported file type. Only PDF, XLS, XLSX, TXT, CSV, PNG, JPG, JPEG, DOC, and DOCX are allowed.",
            )
        return None


class ImageValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, image_extensions, image_validator):
        self.image_extensions = image_extensions
        self.image_validator = image_validator

    def apply(self, uploaded_file, ext):
        if ext in self.image_extensions:
            return self.image_validator(uploaded_file)
        return None


class FileSizeValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, max_file_size, file_too_large_error):
        self.max_file_size = max_file_size
        self.file_too_large_error = file_too_large_error

    def apply(self, uploaded_file, ext):
        if uploaded_file.size > self.max_file_size:
            return False, self.file_too_large_error
        return None


class MimeTypeValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, mime_validator):
        self.mime_validator = mime_validator

    def apply(self, uploaded_file, ext):
        is_valid_mime, mime_error = self.mime_validator(uploaded_file, ext)
        if not is_valid_mime:
            return False, mime_error
        return None


class ExcelSheetValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, excel_extensions, excel_sheet_validator):
        self.excel_extensions = excel_extensions
        self.excel_sheet_validator = excel_sheet_validator

    def apply(self, uploaded_file, ext):
        if ext not in self.excel_extensions:
            return None

        is_valid_excel, excel_error = self.excel_sheet_validator(uploaded_file, ext)
        if not is_valid_excel:
            return False, excel_error

        return None


class WordValidationStrategy(BaseFileValidationStrategy):
    def __init__(self, word_extensions, word_validator):
        self.word_extensions = word_extensions
        self.word_validator = word_validator

    def apply(self, uploaded_file, ext):
        if ext not in self.word_extensions:
            return None

        is_valid_word, word_error = self.word_validator(uploaded_file, ext)
        if not is_valid_word:
            return False, word_error

        return None


class FileValidator:
    def __init__(self, strategies):
        self.strategies = strategies

    def validate(self, uploaded_file):
        ext = os.path.splitext(uploaded_file.name)[1].lower()

        for strategy in self.strategies:
            result = strategy.apply(uploaded_file, ext)
            if result is not None:
                return result

        return True, None
