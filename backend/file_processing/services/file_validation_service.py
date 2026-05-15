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
    validators = _resolve_validators(
        validate_image_func=validate_image_func,
        validate_mime_type_func=validate_mime_type_func,
        validate_excel_sheet_count_func=validate_excel_sheet_count_func,
        validate_word_func=validate_word_func,
    )

    if ext in IMAGE_EXTENSIONS:
        return _validate_image_content(uploaded_file, validators["image"])

    common_result = _validate_common_content(uploaded_file, ext, validators["mime"])
    if not common_result.is_valid:
        return common_result

    return _validate_type_specific_content(uploaded_file, ext, validators)


def _resolve_validators(
    *,
    validate_image_func=None,
    validate_mime_type_func=None,
    validate_excel_sheet_count_func=None,
    validate_word_func=None,
):
    return {
        "image": validate_image_func or validate_image,
        "mime": validate_mime_type_func or validate_mime_type,
        "excel": validate_excel_sheet_count_func or validate_excel_sheet_count,
        "word": validate_word_func or word_validation_service.validate_word,
    }


def _validate_image_content(uploaded_file, validate_image_func) -> ValidationResult:
    is_valid, error = validate_image_func(uploaded_file)
    if not is_valid:
        return ValidationResult.fail(error or "Invalid image file.")
    return ValidationResult.ok()


def _validate_common_content(
    uploaded_file,
    ext,
    validate_mime_type_func,
) -> ValidationResult:
    if uploaded_file.size > MAX_FILE_SIZE:
        return ValidationResult.fail(FILE_TOO_LARGE_ERROR)

    is_valid_mime, mime_error = validate_mime_type_func(uploaded_file, ext)
    if not is_valid_mime:
        return ValidationResult.fail(mime_error or MIME_TYPE_DETECTION_ERROR)

    return ValidationResult.ok()


def _validate_type_specific_content(uploaded_file, ext, validators) -> ValidationResult:
    if ext in {EXT_XLS, EXT_XLSX}:
        return _validate_excel_content(uploaded_file, ext, validators["excel"])

    if ext in {EXT_DOC, EXT_DOCX}:
        return _validate_word_content(uploaded_file, ext, validators["word"])

    return ValidationResult.ok()


def _validate_excel_content(
    uploaded_file,
    ext,
    validate_excel_sheet_count_func,
) -> ValidationResult:
    is_valid, error = validate_excel_sheet_count_func(uploaded_file, ext)
    if not is_valid:
        return ValidationResult.fail(error or EXCEL_CORRUPT_ERROR)
    return ValidationResult.ok()


def _validate_word_content(uploaded_file, ext, validate_word_func) -> ValidationResult:
    is_valid, error = validate_word_func(uploaded_file, ext)
    if not is_valid:
        return ValidationResult.fail(error or WORD_CORRUPT_ERROR)
    return ValidationResult.ok()
