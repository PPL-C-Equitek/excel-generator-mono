import os
import magic
import logging
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from .excel_service import process_uploaded_excel
from .txt_service import process_uploaded_txt
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from file_processing.services.ocr_service import OCRService
from file_processing.services.non_ocr_pdf_service import NonOCRPDFService
from file_processing.services.image_validation_service import validate_image
from file_processing.extractors.image_extractor import ImageExtractor
from file_processing.utils.upload_constants import MAX_FILE_SIZE, FILE_TOO_LARGE_ERROR

logger = logging.getLogger(__name__)

EXT_XLSX = ".xlsx"
EXT_XLS = ".xls"
EXT_PDF = ".pdf"
EXT_TXT = ".txt"
EXT_PNG = ".png"
EXT_JPG = ".jpg"
EXT_JPEG = ".jpeg"

IMAGE_EXTENSIONS = {EXT_PNG, EXT_JPG, EXT_JPEG}
ALLOWED_EXTENSIONS = [EXT_PDF, EXT_XLS, EXT_XLSX, EXT_PNG, EXT_JPG, EXT_JPEG, EXT_TXT]
ALLOWED_MIME_TYPES = {
    EXT_PDF: [
        "application/pdf",
        "application/x-pdf",
        "application/vnd.pdf",
    ],

    EXT_XLS: [
        "application/vnd.ms-excel",
        "application/msexcel",
        "application/x-msexcel",
        "application/x-ms-excel",
        "application/x-excel",
        "application/xls",
        "application/x-xls",
        "application/octet-stream",
        "application/x-ole-storage",
        "application/CDFV2",
        "application/vnd.ms-office",
    ],

    EXT_XLSX: [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/x-zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ],

    EXT_TXT: [
        "text/plain",
        "text/x-log",
    ],
}
MAX_PDF_PAGES = 100
MAX_EXCEL_SHEETS = 100
PDF_CORRUPT_ERROR = "PDF file is corrupt or has an invalid structure."
EXCEL_CORRUPT_ERROR = "Invalid or corrupted Excel file."
EXCEL_TOO_MANY_SHEETS_ERROR = (
    f"Excel has too many sheets (maximum {MAX_EXCEL_SHEETS})."
)
EXCEL_PASSWORD_PROTECTED_ERROR = (
    "Excel file is password-protected. Please remove the password and try again."
)
TXT_CORRUPT_ERROR = "File teks tidak dapat dibaca atau rusak (corrupt)."
TXT_PROTECTED_ERROR = (
    "File terdeteksi sebagai format terproteksi atau terenkripsi. "
    "Pastikan file adalah teks biasa (.txt) yang tidak diproteksi."
)
FILE_EXTENSION_MISMATCH_ERROR = "File content does not match its extension."
OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
ZIP_SIGNATURE_PREFIX = b"PK"

BINARY_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x50\x4B\x03\x04", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\x50\x4B\x05\x06", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1", TXT_PROTECTED_ERROR),
    (b"\x7fELF", FILE_EXTENSION_MISMATCH_ERROR),
    (b"MZ", FILE_EXTENSION_MISMATCH_ERROR),
    (b"%PDF", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\xff\xd8\xff", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\x89PNG", FILE_EXTENSION_MISMATCH_ERROR),
]

def _has_extracted_text(extracted_data):
    """Return True if any page contains extracted text."""
    if not extracted_data or "content" not in extracted_data:
        return False

    for page in extracted_data["content"]:
        if page.get("text"):
            return True

    return False


def _get_empty_page_numbers(extracted_data):
    """Return list of page numbers whose 'text' list is empty."""
    empty = []
    if not extracted_data or "content" not in extracted_data:
        return empty
    for page in extracted_data["content"]:
        if not page.get("text"):
            empty.append(page["page"])
    return empty


def _process_pdf(file_path, uploaded_file):
    is_valid, error = validate_pdf(uploaded_file)
    if not is_valid:
        return False, error, None

    try:
        extracted_data = NonOCRPDFService.extract_non_ocr_pdf_to_json(file_path)

        if not _has_extracted_text(extracted_data):
            # Fully scanned PDF — run OCR on all pages
            extracted_data = OCRService.process_pdf(file_path)
        else:
            # Check for mixed PDF (some pages have text, some don't)
            empty_pages = _get_empty_page_numbers(extracted_data)
            if empty_pages:
                ocr_data = OCRService.process_pdf_pages(file_path, empty_pages)
                # Merge OCR results into the extracted data
                ocr_by_page = {
                    p["page"]: p for p in ocr_data.get("content", [])
                }
                for page in extracted_data["content"]:
                    if page["page"] in ocr_by_page:
                        page["text"] = ocr_by_page[page["page"]]["text"]

    except Exception:
        logger.exception("Non-OCR extraction failed, fallback to OCR")
        extracted_data = OCRService.process_pdf(file_path)

    return True, None, extracted_data


def _process_image(file_path):
    try:
        extractor = ImageExtractor()
        extracted_data = extractor.extract(file_path)
        return True, None, extracted_data
    except ValueError as exc:
        return False, str(exc), None
    except Exception:
        logger.exception("Image extraction failed.")
        return False, "Image OCR extraction failed.", None


def _dispatch_upload_processing(ext, file_path, uploaded_file):
    processors = {
        EXT_PDF: lambda: _process_pdf(file_path, uploaded_file),
        EXT_XLS: lambda: process_uploaded_excel(file_path),
        EXT_XLSX: lambda: process_uploaded_excel(file_path),
        EXT_TXT: lambda: process_uploaded_txt(file_path),
        EXT_PNG: lambda: _process_image(file_path),
        EXT_JPG: lambda: _process_image(file_path),
        EXT_JPEG: lambda: _process_image(file_path),
    }

    processor = processors.get(ext)
    if processor is None:
        return False, "Unsupported file type", None

    return processor()


def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    # Temporary image path: validation has passed, but extraction is not implemented yet.
    # Return upload success without extracted payload.
    if ext in IMAGE_EXTENSIONS:
        return True, None, None, None

    file_path = save_temp_file(uploaded_file)

    try:
        success, error, extracted_data = _dispatch_upload_processing(
            ext,
            file_path,
            uploaded_file,
        )
        if not success:
            return False, error, None, None

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception("Failed to delete temporary upload file.")

    return True, None, None, extracted_data


def validate_file(uploaded_file):
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    # Validate extension
    if ext not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Only PDF, XLS, XLSX, TXT, PNG, JPG, and JPEG are allowed."

    # Image files have their own dedicated validation pipeline
    if ext in IMAGE_EXTENSIONS:
        return validate_image(uploaded_file)

    # Validate size
    if uploaded_file.size > MAX_FILE_SIZE:
        return False, FILE_TOO_LARGE_ERROR

    # Validate MIME type
    is_valid_mime, mime_error = validate_mime_type(uploaded_file, ext)
    if not is_valid_mime:
        return False, mime_error

    if ext in {EXT_XLS, EXT_XLSX}:
        is_valid_excel, excel_error = validate_excel_sheet_count(uploaded_file, ext)
        if not is_valid_excel:
            return False, excel_error

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
        return False, "PDF file is password-protected."
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


def validate_excel_sheet_count(uploaded_file, ext):
    try:
        if _should_parse_as_xls(uploaded_file, ext):
            sheet_count = _get_xls_sheet_count(uploaded_file)
        else:
            sheet_count = _get_xlsx_sheet_count(uploaded_file)
    except Exception:
        logger.exception("Failed to validate Excel sheet count.")
        return False, EXCEL_CORRUPT_ERROR

    return check_excel_sheet_count(sheet_count)


def check_excel_sheet_count(sheet_count):
    if sheet_count > MAX_EXCEL_SHEETS:
        return False, EXCEL_TOO_MANY_SHEETS_ERROR
    return True, None


def _should_parse_as_xls(uploaded_file, ext):
    if ext == EXT_XLS:
        return True

    if ext == EXT_XLSX and _is_ole_container(uploaded_file):
        return _is_legacy_xls_content(uploaded_file)

    return False


def _get_xlsx_sheet_count(uploaded_file):
    from openpyxl import load_workbook

    uploaded_file.seek(0)
    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    try:
        return len(workbook.sheetnames)
    finally:
        workbook.close()
        uploaded_file.seek(0)


def _get_xls_sheet_count(uploaded_file):
    import xlrd

    uploaded_file.seek(0)
    workbook_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    workbook = xlrd.open_workbook(file_contents=workbook_bytes, on_demand=True)
    try:
        return workbook.nsheets
    finally:
        release_resources = getattr(workbook, "release_resources", None)
        if callable(release_resources):
            release_resources()
        uploaded_file.seek(0)


def validate_mime_type(uploaded_file, ext):
    try:
        uploaded_file.seek(0)
        mime = magic.from_buffer(uploaded_file.read(2048), mime=True)
        uploaded_file.seek(0)

        expected_mimes = ALLOWED_MIME_TYPES.get(ext, [])

        if ext == EXT_XLSX and _is_ole_container(uploaded_file):
            if _is_legacy_xls_content(uploaded_file):
                # Allow legacy .xls content uploaded under .xlsx extension.
                return True, None
            return False, EXCEL_PASSWORD_PROTECTED_ERROR

        if ext == EXT_XLSX and not _has_zip_signature(uploaded_file):
            return False, FILE_EXTENSION_MISMATCH_ERROR

        if ext == EXT_TXT:
            return _validate_txt_content(uploaded_file, mime)

        if mime not in expected_mimes:
            return False, FILE_EXTENSION_MISMATCH_ERROR

        return True, None

    except Exception:
        return False, "Unable to determine file type."


def _is_ole_container(uploaded_file):
    """Return True if file starts with OLE Compound File signature."""
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(len(OLE_SIGNATURE))
        uploaded_file.seek(0)
        return header == OLE_SIGNATURE
    except Exception:
        return False


def _is_legacy_xls_content(uploaded_file):
    """
    Best-effort check for real legacy .xls content to avoid mislabeling it
    as password-protected .xlsx.
    """
    try:
        import xlrd
    except Exception:
        return False

    try:
        uploaded_file.seek(0)
        content = uploaded_file.read()
        uploaded_file.seek(0)
        xlrd.open_workbook(file_contents=content, on_demand=True)
        return True
    except Exception:
        return False


def _has_zip_signature(uploaded_file):
    """Return True if file starts with ZIP signature prefix."""
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(len(ZIP_SIGNATURE_PREFIX))
        uploaded_file.seek(0)
        return header == ZIP_SIGNATURE_PREFIX
    except Exception:
        return False

def _has_binary_signature(uploaded_file):
    try:
        max_prefix = max(len(sig) for sig, _ in BINARY_SIGNATURES)
        uploaded_file.seek(0)
        header = uploaded_file.read(max_prefix)
        uploaded_file.seek(0)

        for signature, error_msg in BINARY_SIGNATURES:
            if header.startswith(signature):
                return True, error_msg

        return False, None
    except Exception:
        return False, None

def _validate_txt_content(uploaded_file, detected_mime: str):
    is_binary, binary_error = _has_binary_signature(uploaded_file)
    if is_binary:
        return False, binary_error

    if detected_mime and detected_mime.startswith("text/"):
        return True, None

    allowed = ALLOWED_MIME_TYPES.get(EXT_TXT, [])
    if detected_mime in allowed:
        return True, None

    return False, TXT_CORRUPT_ERROR


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
