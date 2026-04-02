import os
import logging
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from .excel_service import process_uploaded_excel
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from file_processing.services.ocr_service import OCRService
from file_processing.services.non_ocr_pdf_service import NonOCRPDFService
from file_processing.services import word_validation_service

try:
    import magic
except Exception:  # pragma: no cover - optional dependency in local envs
    class _MagicShim:
        @staticmethod
        def from_buffer(_buffer, mime=True):
            raise ImportError("python-magic unavailable")

    magic = _MagicShim()

logger = logging.getLogger(__name__)

EXT_XLSX = ".xlsx"
EXT_XLS = ".xls"
EXT_PDF = ".pdf"
EXT_DOCX = ".docx"
EXT_DOC = ".doc"
MIME_OCTET_STREAM = "application/octet-stream"
MIME_OLE_STORAGE = "application/x-ole-storage"
MIME_ZIP = "application/zip"

ALLOWED_EXTENSIONS = [EXT_PDF, EXT_XLS, EXT_XLSX, EXT_DOCX, EXT_DOC]
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
        MIME_OCTET_STREAM,
        MIME_OLE_STORAGE,
        "application/CDFV2",
        "application/vnd.ms-office",
    ],

    EXT_XLSX: [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        MIME_ZIP,
        "application/x-zip",
        "application/x-zip-compressed",
        MIME_OCTET_STREAM,
    ],

    EXT_DOC: [
        "application/msword",
        "application/doc",
        "application/vnd.ms-word",
        "application/x-msword",
        MIME_OCTET_STREAM,
        MIME_OLE_STORAGE,
        "application/CDFV2",
    ],

    EXT_DOCX: [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        MIME_ZIP,
        "application/x-zip",
        "application/x-zip-compressed",
        MIME_OCTET_STREAM,
        MIME_OLE_STORAGE,
    ],
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FILE_TOO_LARGE_ERROR = "File too large. Maximum allowed size is 10MB."
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
MAX_WORD_PAGES = word_validation_service.MAX_WORD_PAGES
WORD_CORRUPT_ERROR = word_validation_service.WORD_CORRUPT_ERROR
OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
ZIP_SIGNATURE_PREFIX = b"PK"
DOES_NOT_MATCH_EXTENSION_ERROR = "File content does not match its extension."

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

def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    file_path = save_temp_file(uploaded_file)
    extracted_data = None

    try:
        if ext == ".pdf":
            success, error, data = _process_pdf(file_path, uploaded_file)
            if not success:
                return False, error, None, None
            extracted_data = data

        elif ext in [".xlsx", ".xls"]:
            success, error, data = process_uploaded_excel(file_path)
            if not success:
                return False, error, None, None
            extracted_data = data

        else:
            return False, "Unsupported file type", None, None

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
        return False, "Unsupported file type. Only PDF, XLS, XLSX, DOC, and DOCX are allowed."

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

    if ext in {EXT_DOC, EXT_DOCX}:
        is_valid_word, word_error = word_validation_service.validate_word(uploaded_file, ext)
        if not is_valid_word:
            return False, word_error

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
        head = _read_head(uploaded_file)
        mime = _detect_mime(head, ext)

        if not mime:
            return False, "Unable to determine file type."

        expected_mimes = ALLOWED_MIME_TYPES.get(ext, [])

        # === IMPORTANT: urutan ini jangan diubah ===

        if ext == EXT_XLSX and _is_ole_container(uploaded_file):
            if _is_legacy_xls_content(uploaded_file):
                return True, None
            return False, EXCEL_PASSWORD_PROTECTED_ERROR

        if ext == EXT_XLSX and not _has_zip_signature(uploaded_file):
            return False, DOES_NOT_MATCH_EXTENSION_ERROR

        if ext == EXT_DOC and not _is_ole_container(uploaded_file):
            return False, DOES_NOT_MATCH_EXTENSION_ERROR

        if ext == EXT_DOCX and not _has_zip_signature(uploaded_file):
            return False, DOES_NOT_MATCH_EXTENSION_ERROR

        if mime not in expected_mimes:
            return False, DOES_NOT_MATCH_EXTENSION_ERROR

        return True, None

    except Exception:
        return False, "Unable to determine file type."

def _read_head(uploaded_file, size=2048):
    uploaded_file.seek(0)
    head = uploaded_file.read(size)
    uploaded_file.seek(0)
    return head


def _detect_mime(head, ext):
    try:
        return magic.from_buffer(head, mime=True)
    except Exception:
        return _fallback_mime(head, ext)


def _fallback_mime(head, ext):
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(ZIP_SIGNATURE_PREFIX):
        return MIME_ZIP
    if head.startswith(OLE_SIGNATURE):
        return MIME_OLE_STORAGE
    if ext in {EXT_XLS, EXT_DOC}:
        return MIME_OCTET_STREAM
    return None

# def validate_mime_type(uploaded_file, ext):
#     try:
#         uploaded_file.seek(0)
#         head = uploaded_file.read(2048)
#         uploaded_file.seek(0)
        
#         try:
#             mime = magic.from_buffer(head, mime=True) 
#         except Exception:
#             # Fallback MIME sniffing for environments without libmagic.
#             if head.startswith(b"%PDF"):
#                 mime = "application/pdf"
#             elif head.startswith(ZIP_SIGNATURE_PREFIX):
#                 mime = MIME_ZIP
#             elif head.startswith(OLE_SIGNATURE):
#                 mime = MIME_OLE_STORAGE
#             elif ext in {EXT_XLS, EXT_DOC}:
#                 mime = MIME_OCTET_STREAM
#             else:
#                 mime = None
        
#         if not mime:
#             return False, "Unable to determine file type."
        
#         expected_mimes = ALLOWED_MIME_TYPES.get(ext, [])
        
#         if ext == EXT_XLSX and _is_ole_container(uploaded_file):
#             if _is_legacy_xls_content(uploaded_file):
#                 # Allow legacy .xls content uploaded under .xlsx extension.
#                 return True, None
#             return False, EXCEL_PASSWORD_PROTECTED_ERROR
        
#         if ext == EXT_XLSX and not _has_zip_signature(uploaded_file):
#             return False, DOES_NOT_MATCH_EXTENSION_ERROR
        
#         if ext == EXT_DOC and not _is_ole_container(uploaded_file):
#             return False, DOES_NOT_MATCH_EXTENSION_ERROR
        
#         if ext == EXT_DOCX and not _has_zip_signature(uploaded_file):
#             return False, DOES_NOT_MATCH_EXTENSION_ERROR
        
#         if mime not in expected_mimes:
#             return False, DOES_NOT_MATCH_EXTENSION_ERROR
        
#         return True, None
    
#     except Exception:
#         return False, "Unable to determine file type."


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
