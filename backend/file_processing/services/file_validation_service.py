"""High-level upload validation routing."""

import os

from file_processing.services import word_validation_service
from file_processing.services.contracts import ValidationResult
from file_processing.services.excel_validation_service import validate_excel_sheet_count
from file_processing.services.image_validation_service import validate_image
from file_processing.services.mime_validation_service import validate_mime_type
from file_processing.utils.upload_constants import FILE_TOO_LARGE_ERROR, MAX_FILE_SIZE
from file_processing.services.upload_file_types import (
    ALLOWED_EXTENSIONS,
    EXCEL_CORRUPT_ERROR,
    EXT_DOC,
    EXT_DOCX,
    EXT_XLS,
    EXT_XLSX,
    IMAGE_EXTENSIONS,
    MIME_TYPE_DETECTION_ERROR,
    UNSUPPORTED_FILE_TYPE_ERROR,
    WORD_CORRUPT_ERROR,
)


def validate_file_result(
    uploaded_file,
    *,
    validate_image_func=None,
    validate_mime_type_func=None,
    validate_excel_sheet_count_func=None,
    validate_word_func=None,
) -> ValidationResult:
    """Validate uploaded file and return ValidationResult."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return ValidationResult.fail(UNSUPPORTED_FILE_TYPE_ERROR)

    return _validate_file_content(
        uploaded_file,
        ext,
        validate_image_func=validate_image_func,
        validate_mime_type_func=validate_mime_type_func,
        validate_excel_sheet_count_func=validate_excel_sheet_count_func,
        validate_word_func=validate_word_func,
    )


def _validate_file_content(
    uploaded_file,
    ext,
    *,
    validate_image_func=None,
    validate_mime_type_func=None,
    validate_excel_sheet_count_func=None,
    validate_word_func=None,
) -> ValidationResult:
    """Validate file size, MIME type, and type-specific constraints."""
    validate_image_func = validate_image_func or validate_image
    validate_mime_type_func = validate_mime_type_func or validate_mime_type
    validate_excel_sheet_count_func = (
        validate_excel_sheet_count_func or validate_excel_sheet_count
    )
    validate_word_func = validate_word_func or word_validation_service.validate_word

    # Image files can return early without further checks
    if ext in IMAGE_EXTENSIONS:
        is_valid, error = validate_image_func(uploaded_file)
        if not is_valid:
            return ValidationResult.fail(error or "Invalid image file.")
        return ValidationResult.ok()

    # All other file types: check size and MIME type
    if uploaded_file.size > MAX_FILE_SIZE:
        return ValidationResult.fail(FILE_TOO_LARGE_ERROR)

    is_valid_mime, mime_error = validate_mime_type_func(uploaded_file, ext)
    if not is_valid_mime:
        return ValidationResult.fail(mime_error or MIME_TYPE_DETECTION_ERROR)

    # Type-specific format validation
    if ext in {EXT_XLS, EXT_XLSX}:
        is_valid_excel, excel_error = validate_excel_sheet_count_func(
            uploaded_file,
            ext,
        )
        if not is_valid_excel:
            return ValidationResult.fail(excel_error or EXCEL_CORRUPT_ERROR)

    if ext in {EXT_DOC, EXT_DOCX}:
        is_valid_word, word_error = validate_word_func(uploaded_file, ext)
        if not is_valid_word:
            return ValidationResult.fail(word_error or WORD_CORRUPT_ERROR)

    return ValidationResult.ok()

