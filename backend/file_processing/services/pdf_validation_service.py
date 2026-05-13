"""PDF-specific upload validation."""

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

from file_processing.services.contracts import ValidationResult
from file_processing.services.upload_file_types import (
    MAX_PDF_PAGES,
    PDF_CORRUPT_ERROR,
)


def validate_pdf_result(uploaded_file, *, reader_cls=PdfReader) -> ValidationResult:
    try:
        uploaded_file.seek(0)
        reader = reader_cls(uploaded_file, strict=True)
    except Exception:
        return ValidationResult.fail(PDF_CORRUPT_ERROR)

    is_valid, error = check_pdf_encrypted(reader)
    if not is_valid:
        return ValidationResult.fail(error or PDF_CORRUPT_ERROR)

    is_valid, page_count_or_error = check_pdf_structure(reader)
    if not is_valid:
        return ValidationResult.fail(page_count_or_error or PDF_CORRUPT_ERROR)

    page_count = page_count_or_error
    is_valid, error = check_pdf_page_count(page_count)
    if not is_valid:
        return ValidationResult.fail(error or PDF_CORRUPT_ERROR)

    return ValidationResult.ok()


def check_pdf_encrypted(reader):
    if reader.is_encrypted:
        return False, "PDF file is password-protected."
    return True, None


def check_pdf_structure(reader):
    try:
        return True, len(reader.pages)
    except PdfReadError:
        return False, PDF_CORRUPT_ERROR
    except Exception:
        return False, PDF_CORRUPT_ERROR


def check_pdf_page_count(page_count):
    if page_count > MAX_PDF_PAGES:
        return False, f"PDF exceeds the maximum allowed page count of {MAX_PDF_PAGES}."
    return True, None
