import os
import zipfile
import xml.etree.ElementTree as ET
import logging
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from .excel_service import process_uploaded_excel
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from file_processing.services.ocr_service import OCRService
from file_processing.services.non_ocr_pdf_service import NonOCRPDFService

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
        "application/x-ole-storage",
        "application/CDFV2",
        "application/vnd.ms-office",
    ],

    EXT_XLSX: [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
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
        "application/x-ole-storage",
        "application/CDFV2",
    ],

    EXT_DOCX: [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/x-zip",
        "application/x-zip-compressed",
        MIME_OCTET_STREAM,
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
MAX_WORD_PAGES = 100
WORD_CORRUPT_ERROR = "Word file is corrupt or has an invalid structure."
OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
ZIP_SIGNATURE_PREFIX = b"PK"

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
        is_valid_word, word_error = validate_word(uploaded_file, ext)
        if not is_valid_word:
            return False, word_error

    return True, None


def validate_word(uploaded_file, ext):
    """Single-parse Word validation: encryption, structure, and page count."""
    if ext == EXT_DOCX:
        is_valid, error = check_docx_encrypted(uploaded_file)
        if not is_valid:
            return False, error

        is_valid, page_count_or_error = check_docx_structure(uploaded_file)
        if not is_valid:
            return False, page_count_or_error

        page_count = page_count_or_error
    elif ext == EXT_DOC:
        is_valid, error = check_doc_encrypted(uploaded_file)
        if not is_valid:
            return False, error

        is_valid, page_count_or_error = check_doc_structure(uploaded_file)
        if not is_valid:
            return False, page_count_or_error

        page_count = page_count_or_error
    else:
        return False, "Unsupported file type."

    is_valid, error = check_word_page_count(page_count)
    if not is_valid:
        return False, error

    return True, None


def check_docx_encrypted(uploaded_file):
    # Encrypted OOXML files are wrapped in OLE container, not regular ZIP-based DOCX.
    if _is_ole_container(uploaded_file):
        return False, "Word file is password-protected."
    return True, None


def check_docx_structure(uploaded_file):
    try:
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return False, WORD_CORRUPT_ERROR

            page_count = _extract_docx_page_count(archive)
            return True, page_count
    except Exception:
        return False, WORD_CORRUPT_ERROR
    finally:
        uploaded_file.seek(0)


def _extract_docx_page_count(archive):
    try:
        app_xml = archive.read("docProps/app.xml")
        root = ET.fromstring(app_xml)
        for element in root.iter():
            if element.tag.endswith("Pages") and element.text:
                return max(int(element.text), 0)
    except Exception:
        return 0

    return 0


def check_doc_encrypted(uploaded_file):
    if not _is_ole_container(uploaded_file):
        return False, WORD_CORRUPT_ERROR

    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(4096)
        uploaded_file.seek(0)
        if b"EncryptedPackage" in head or b"EncryptionInfo" in head:
            return False, "Word file is password-protected."
    except Exception:
        return False, WORD_CORRUPT_ERROR

    return True, None


def check_doc_structure(uploaded_file):
    if not _is_ole_container(uploaded_file):
        return False, WORD_CORRUPT_ERROR

    try:
        uploaded_file.seek(0)
        content = uploaded_file.read(1024 * 1024)
        uploaded_file.seek(0)

        if b"WordDocument" not in content:
            return False, WORD_CORRUPT_ERROR

        return True, 0
    except Exception:
        return False, WORD_CORRUPT_ERROR


def check_word_page_count(page_count):
    if page_count > MAX_WORD_PAGES:
        return (
            False,
            f"Word exceeds the maximum allowed page count of {MAX_WORD_PAGES}.",
        )
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
        head = uploaded_file.read(2048)
        uploaded_file.seek(0)

        try:
            mime = magic.from_buffer(head, mime=True)
        except Exception:
            # Fallback MIME sniffing for environments without libmagic.
            if head.startswith(b"%PDF"):
                mime = "application/pdf"
            elif head.startswith(ZIP_SIGNATURE_PREFIX):
                mime = "application/zip"
            elif head.startswith(OLE_SIGNATURE):
                mime = "application/x-ole-storage"
            elif ext in {EXT_XLS, EXT_DOC}:
                mime = MIME_OCTET_STREAM
            else:
                mime = None

        if not mime:
            return False, "Unable to determine file type."

        expected_mimes = ALLOWED_MIME_TYPES.get(ext, [])

        if ext == EXT_XLSX and _is_ole_container(uploaded_file):
            if _is_legacy_xls_content(uploaded_file):
                # Allow legacy .xls content uploaded under .xlsx extension.
                return True, None
            return False, EXCEL_PASSWORD_PROTECTED_ERROR

        if ext == EXT_XLSX and not _has_zip_signature(uploaded_file):
            return False, "File content does not match its extension."

        if ext == EXT_DOC and not _is_ole_container(uploaded_file):
            return False, "File content does not match its extension."

        if ext == EXT_DOCX and not _has_zip_signature(uploaded_file):
            return False, "File content does not match its extension."

        if mime not in expected_mimes:
            return False, "File content does not match its extension."

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
