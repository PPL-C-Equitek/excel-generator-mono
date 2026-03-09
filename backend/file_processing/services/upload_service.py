import os
import magic
import logging
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from file_processing.services.ocr_service import OCRService

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]
ALLOWED_MIME_TYPES = {
    ".pdf": ["application/pdf"],
    ".xls": [
        "application/vnd.ms-excel",
        "application/octet-stream",
    ],
    ".xlsx": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/x-zip",
        "application/octet-stream",
    ],
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PDF_PAGES = 100


def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    is_valid, error = validate_mime_type(uploaded_file, ext)
    if not is_valid:
        return False, error, None, None

    if ext == ".pdf":
        is_valid, error = validate_pdf_not_corrupt(uploaded_file)
        if not is_valid:
            return False, error, None, None

        is_valid, error = validate_pdf_not_password_protected(uploaded_file)
        if not is_valid:
            return False, error, None, None

        is_valid, error = validate_pdf_page_count(uploaded_file)
        if not is_valid:
            return False, error, None

    file_path = save_temp_file(uploaded_file)

    extracted_text = None

    try:
        if ext == ".pdf":
            extracted_text = OCRService.process_pdf(file_path)

    except Exception:
        logger.exception(
            "OCR failed for uploaded PDF: %s. File saved at %s",
            uploaded_file.name,
            file_path,
        )
        extracted_text = None

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception("Failed to delete temporary file: %s", file_path)

    return True, None, file_path, extracted_text


def validate_file(uploaded_file):
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Only PDF, XLS, and XLSX are allowed."

    # Validate size
    if uploaded_file.size > MAX_FILE_SIZE:
        return False, "File too large. Maximum allowed size is 10MB."

    return True, None


def validate_pdf_not_corrupt(uploaded_file):
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file, strict=True)

        if reader.is_encrypted:
            return True, None

        _ = len(reader.pages)
        return True, None

    except PdfReadError:
        return False, "The PDF file is corrupt or has an invalid structure."
    except Exception:
        return False, "The PDF file is corrupt or has an invalid structure."


def validate_pdf_not_password_protected(uploaded_file):
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)

        if reader.is_encrypted:
            return False, "The PDF file is password-protected."

        return True, None

    except Exception:
        return False, "The PDF file is password-protected and cannot be accessed"


def validate_pdf_page_count(uploaded_file):
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)

        if len(reader.pages) > MAX_PDF_PAGES:
            return (
                False,
                f"PDF exceeds the maximum allowed page count of {MAX_PDF_PAGES}.",
            )

        return True, None

    except Exception:
        return False, "Unable to read PDF page count."


def validate_mime_type(uploaded_file, ext):
    try:
        uploaded_file.seek(0)
        mime = magic.from_buffer(uploaded_file.read(2048), mime=True)
        uploaded_file.seek(0)

        expected_mimes = ALLOWED_MIME_TYPES.get(ext, [])

        if mime not in expected_mimes:
            return False, "File content does not match its extension."

        return True, None

    except Exception:
        return False, "Unable to determine file type."


def save_temp_file(uploaded_file):
    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)

    original_name = os.path.basename(uploaded_file.name)

    safe_name = get_valid_filename(original_name)

    unique_name = f"{uuid4()}_{safe_name}"

    base_dir = os.path.abspath(settings.UPLOAD_TEMP_DIR)
    file_path = os.path.abspath(os.path.join(base_dir, unique_name))

    if not file_path.startswith(base_dir):
        raise ValueError("Invalid file path detected.")

    with open(file_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return file_path
