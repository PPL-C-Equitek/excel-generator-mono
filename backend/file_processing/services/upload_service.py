import os
import magic
import logging
import pdfplumber
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
PDF_CORRUPT_ERROR = "The PDF file is corrupt or has an invalid structure."


def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    is_valid, error = validate_mime_type(uploaded_file, ext)
    if not is_valid:
        return False, error, None, None

    if ext == ".pdf":
        is_valid, error = validate_pdf(uploaded_file)
        if not is_valid:
            return False, error, None, None

    file_path = save_temp_file(uploaded_file)

    extracted_text = None

    try:
        if ext == ".pdf":
            extracted_text = OCRService.process_pdf(file_path)

    except Exception:
        logger.exception("OCR processing failed for uploaded PDF.")
        extracted_text = None

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception("Failed to delete temporary upload file.")

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


def extract_pdf_to_json(file_path: str) -> dict:
    """
    Extract text content from a non-OCR PDF file and return structured JSON.

    Each page is parsed for tables first (via pdfplumber). If tables are found,
    each row becomes a list of cell strings. Any text outside tables is captured
    as plain-text lines. If no tables are detected the page text is split into
    individual lines.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        dict with structure:
        {
            "document_info": {
                "source_type": "pdf",
                "file_name": "<original filename>",
                "total_pages": <int>
            },
            "content": [
                {
                    "page": 1,
                    "text": [
                        ["col1", "col2", ...],   // table row
                        ["col1", "col2", ...],
                        "plain text line",        // non-table text
                    ]
                },
                ...
            ]
        }

    Raises:
        FileNotFoundError: If the file does not exist.
    """

    pdf = pdfplumber.open(file_path)
    pages_content = []

    for page_number, page in enumerate(pdf.pages, start=1):
        page_data: list = []

        tables = page.extract_tables() or []
        table_bboxes = [t.bbox for t in page.find_tables()] if tables else []

        if tables:
            # Collect text outside table regions
            filtered_page = page
            for bbox in table_bboxes:
                filtered_page = filtered_page.outside_bbox(bbox)

            outside_text = filtered_page.extract_text() or ""
            outside_lines = outside_text.splitlines() if outside_text else []

            # Add table rows
            for table in tables:
                for row in table:
                    page_data.append([cell if cell is not None else "" for cell in row])

            # Add non-table text lines
            for line in outside_lines:
                stripped = line.strip()
                if stripped:
                    page_data.append(stripped)
        else:
            raw_text = page.extract_text() or ""
            if raw_text:
                page_data = raw_text.splitlines()
            # else: page_data stays []

        pages_content.append(
            {
                "page": page_number,
                "text": page_data,
            }
        )

    total_pages = len(pdf.pages)
    pdf.close()

    file_name = os.path.basename(file_path)

    return {
        "document_info": {
            "source_type": "pdf",
            "file_name": file_name,
            "total_pages": total_pages,
        },
        "content": pages_content,
    }
