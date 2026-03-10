import os
import magic
import logging
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from .excel_service import process_uploaded_excel
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from file_processing.services.ocr_service import OCRService
from file_processing.services.non_ocr_pdf_service import NonOCRPDFService

logger = logging.getLogger(__name__)

EXT_XLSX = ".xlsx"
EXT_XLS = ".xls"
EXT_PDF = ".pdf"

ALLOWED_EXTENSIONS = [EXT_PDF, EXT_XLS, EXT_XLSX]
ALLOWED_MIME_TYPES = {
    EXT_PDF: ["application/pdf"],
    EXT_XLS: [
        "application/vnd.ms-excel",
        "application/octet-stream",
    ],
    EXT_XLSX: [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/x-zip",
        "application/octet-stream",
    ],
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_PDF_PAGES = 100
PDF_CORRUPT_ERROR = "The PDF file is corrupt or has an invalid structure."


def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    is_valid, error = validate_mime_type(uploaded_file, ext)
    if not is_valid:
        return False, error, None, None

    file_path = save_temp_file(uploaded_file)

    extracted_data = None

    try:
        # -------- PDF handling --------
        if ext == ".pdf":
            is_valid, error = validate_pdf(uploaded_file)
            if not is_valid:
                return False, error, None, None

            try:
                # try normal extraction first
                extracted_data = NonOCRPDFService.extract_non_ocr_pdf_to_json(file_path)

                # if empty -> fallback to OCR
                if not extracted_data:
                    extracted_data = OCRService.process_pdf(file_path)

            except Exception:
                logger.exception("Non-OCR extraction failed, fallback to OCR")
                extracted_data = OCRService.process_pdf(file_path)

        # -------- Excel handling --------
        elif ext in [EXT_XLSX, EXT_XLS]:
            success, error, data = process_uploaded_excel(file_path)

            if not success:
                return False, error, None, None

            extracted_data = data

        else:
            return False, "Unsupported file type", None, None

    except Exception:
        logger.exception("Processing failed.")
        return False, "File processing failed", None, None

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception("Failed to delete temporary upload file.")

    return True, None, file_path, extracted_data


def validate_file(uploaded_file):
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Only PDF, XLS, and XLSX are allowed."

    # Validate size
    if uploaded_file.size > MAX_FILE_SIZE:
        return False, "File too large. Maximum allowed size is 10MB."

    # Validate MIME type
    is_valid_mime, mime_error = validate_mime_type(uploaded_file, ext)
    if not is_valid_mime:
        return False, mime_error

    return True, None


def validate_pdf(uploaded_file):
    """Single-parse PDF validation: encryption, structure, and page count."""
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file, strict=True)
    except Exception:
        return False, PDF_CORRUPT_ERROR

    is_valid, error = check_pdf_encrypted(reader)
    if not is_valid:
        return False, error

    is_valid, page_count_or_error = check_pdf_structure(reader)
    if not is_valid:
        return False, page_count_or_error

    page_count = page_count_or_error

    is_valid, error = check_pdf_page_count(page_count)
    if not is_valid:
        return False, error

    return True, None


def check_pdf_encrypted(reader):
    if reader.is_encrypted:
        return False, "The PDF file is password-protected."
    return True, None


def check_pdf_structure(reader):
    try:
        page_count = len(reader.pages)
        return True, page_count
    except PdfReadError:
        return False, PDF_CORRUPT_ERROR
    except Exception:
        return False, PDF_CORRUPT_ERROR


def check_pdf_page_count(page_count):
    if page_count > MAX_PDF_PAGES:
        return (
            False,
            f"PDF exceeds the maximum allowed page count of {MAX_PDF_PAGES}.",
        )
    return True, None


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
