import os
import logging
from uuid import uuid4

from django.conf import settings
from django.utils.text import get_valid_filename
from PyPDF2 import PdfReader

from .excel_service import process_uploaded_excel
from .txt_service import process_uploaded_txt
from .csv_service import process_uploaded_csv
from file_processing.extractors.image_extractor import ImageExtractor
from file_processing.services.ocr_service import OCRService
from file_processing.services.non_ocr_pdf_service import NonOCRPDFService
from file_processing.services import word_validation_service
from file_processing.services.image_validation_service import validate_image
from file_processing.services.word_extraction_service import WordExtractionService
from file_processing.services.contracts import ValidationResult, ExtractionResult
from file_processing.services import (
    excel_validation_service,
    file_validation_service,
    mime_validation_service,
    pdf_validation_service,
)
from file_processing.services.exceptions import (
    UploadValidationError,
    UploadExtractionError,
    UploadStorageError,
)

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

EXT_TXT = ".txt"
EXT_CSV = ".csv"
EXT_PNG = ".png"
EXT_JPG = ".jpg"
EXT_JPEG = ".jpeg"

MIME_OCTET_STREAM = "application/octet-stream"
MIME_OLE_STORAGE = "application/x-ole-storage"
MIME_ZIP = "application/zip"

IMAGE_EXTENSIONS = {EXT_PNG, EXT_JPG, EXT_JPEG}
ALLOWED_EXTENSIONS = [
    EXT_PDF,
    EXT_XLS,
    EXT_XLSX,
    EXT_PNG,
    EXT_JPG,
    EXT_JPEG,
    EXT_DOCX,
    EXT_DOC,
    EXT_TXT,
    EXT_CSV,
]

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
    EXT_TXT: [
        "text/plain",
        "text/x-log",
    ],
    EXT_CSV: [
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    ],
}

MAX_PDF_PAGES = 100
MAX_EXCEL_SHEETS = 100
PDF_CORRUPT_ERROR = "PDF file is corrupt or has an invalid structure."
EXCEL_CORRUPT_ERROR = "Invalid or corrupted Excel file."
EXCEL_TOO_MANY_SHEETS_ERROR = f"Excel has too many sheets (maximum {MAX_EXCEL_SHEETS})."
EXCEL_PASSWORD_PROTECTED_ERROR = (
    "Excel file is password-protected. Please remove the password and try again."
)
MAX_WORD_PAGES = word_validation_service.MAX_WORD_PAGES
WORD_CORRUPT_ERROR = word_validation_service.WORD_CORRUPT_ERROR
TXT_CORRUPT_ERROR = "File teks tidak dapat dibaca atau rusak (corrupt)."
TXT_PROTECTED_ERROR = (
    "File terdeteksi sebagai format terproteksi atau terenkripsi. "
    "Pastikan file adalah teks biasa (.txt) yang tidak diproteksi."
)
CSV_CORRUPT_ERROR = "File CSV tidak dapat dibaca atau rusak (corrupt)."
CSV_PROTECTED_ERROR = (
    "File CSV terdeteksi sebagai format terproteksi atau terenkripsi. "
    "Pastikan file adalah CSV biasa yang tidak diproteksi."
)
MIME_TYPE_DETECTION_ERROR = "Unable to determine file type."
FILE_EXTENSION_MISMATCH_ERROR = "File content does not match its extension."
ZIP_SIGNATURE_PREFIX = b"PK"
DOES_NOT_MATCH_EXTENSION_ERROR = "File content does not match its extension."
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_SIGNATURE_PREFIX = b"PK"

BINARY_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x50\x4b\x03\x04", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\x50\x4b\x05\x06", FILE_EXTENSION_MISMATCH_ERROR),
    (OLE_SIGNATURE, TXT_PROTECTED_ERROR),
    (b"\x7fELF", FILE_EXTENSION_MISMATCH_ERROR),
    (b"MZ", FILE_EXTENSION_MISMATCH_ERROR),
    (b"%PDF", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\xff\xd8\xff", FILE_EXTENSION_MISMATCH_ERROR),
    (b"\x89PNG", FILE_EXTENSION_MISMATCH_ERROR),
]


def _has_extracted_text(extracted_data):
    if not extracted_data or "content" not in extracted_data:
        return False
    for page in extracted_data["content"]:
        if page.get("text"):
            return True
    return False


def _get_empty_page_numbers(extracted_data):
    empty = []
    if not extracted_data or "content" not in extracted_data:
        return empty
    for page in extracted_data["content"]:
        if not page.get("text"):
            empty.append(page["page"])
    return empty


def _process_pdf_result(file_path, uploaded_file) -> ExtractionResult:
    """Process PDF and return ExtractionResult. Raises UploadValidationError on validation failure."""
    validation_is_valid, validation_error = validate_pdf(uploaded_file)
    validation_result = ValidationResult(
        is_valid=validation_is_valid,
        error=validation_error,
    )
    if not validation_result.is_valid:
        raise UploadValidationError(validation_result.error)

    try:
        extracted_data = NonOCRPDFService.extract_non_ocr_pdf_to_json(file_path)

        if not _has_extracted_text(extracted_data):
            extracted_data = OCRService.process_pdf(file_path)
        else:
            empty_pages = _get_empty_page_numbers(extracted_data)
            if empty_pages:
                ocr_data = OCRService.process_pdf_pages(file_path, empty_pages)
                # Merge OCR results into the extracted data
                ocr_by_page = {p["page"]: p for p in ocr_data.get("content", [])}
                for page in extracted_data["content"]:
                    if page["page"] in ocr_by_page:
                        page["text"] = ocr_by_page[page["page"]]["text"]
        return ExtractionResult.ok(extracted_data)
    except Exception:
        logger.exception("Non-OCR extraction failed, fallback to OCR")
        try:
            extracted_data = OCRService.process_pdf(file_path)
            return ExtractionResult.ok(extracted_data)
        except Exception:
            logger.exception("PDF extraction failed")
            raise


def _process_pdf(file_path, uploaded_file):
    """Legacy wrapper that preserves the tuple return contract."""
    try:
        return _process_pdf_result(file_path, uploaded_file).to_legacy_tuple()
    except UploadValidationError as exc:
        return False, str(exc), None


def _process_image_result(file_path) -> ExtractionResult:
    """Process image extraction and return ExtractionResult."""
    try:
        extractor = ImageExtractor()
        extracted_data = extractor.extract(file_path)
        return ExtractionResult.ok(extracted_data)
    except ValueError as exc:
        return ExtractionResult.fail(str(exc))
    except Exception:
        logger.exception("Image extraction failed.")
        return ExtractionResult.fail("Image OCR extraction failed.")


def _process_word_result(file_path, ext) -> ExtractionResult:
    """Process word extraction and return ExtractionResult."""
    try:
        extracted_data = WordExtractionService.extract_word_to_json(file_path, ext)
    except ValueError as exc:
        return ExtractionResult.fail(str(exc))
    except Exception:
        logger.exception("Word extraction failed")
        return ExtractionResult.fail(WORD_CORRUPT_ERROR)

    return ExtractionResult.ok(extracted_data)


def _convert_extraction_tuple_to_result(result_tuple) -> ExtractionResult:
    """Convert external service tuple result to ExtractionResult."""
    success, error, extracted_data = result_tuple
    if success:
        return ExtractionResult.ok(extracted_data)
    return ExtractionResult.fail(error or "Processing failed")


def _process_uploaded_excel_result(file_path) -> ExtractionResult:
    """Process Excel file and return ExtractionResult."""
    return _convert_extraction_tuple_to_result(process_uploaded_excel(file_path))


def _process_uploaded_txt_result(file_path) -> ExtractionResult:
    """Process TXT file and return ExtractionResult."""
    return _convert_extraction_tuple_to_result(process_uploaded_txt(file_path))


def _process_uploaded_csv_result(file_path) -> ExtractionResult:
    """Process CSV file and return ExtractionResult."""
    return _convert_extraction_tuple_to_result(process_uploaded_csv(file_path))



def _dispatch_upload_processing(ext, file_path, uploaded_file) -> ExtractionResult:
    """Dispatch upload processing by file type. Returns ExtractionResult."""
    processors = {
        EXT_PDF: lambda: _convert_extraction_tuple_to_result(
            _process_pdf(file_path, uploaded_file)
        ),
        EXT_XLS: lambda: _process_uploaded_excel_result(file_path),
        EXT_XLSX: lambda: _process_uploaded_excel_result(file_path),
        EXT_DOC: lambda: _convert_extraction_tuple_to_result(
            process_word(file_path, EXT_DOC)
        ),
        EXT_DOCX: lambda: _convert_extraction_tuple_to_result(
            process_word(file_path, EXT_DOCX)
        ),
        EXT_TXT: lambda: _process_uploaded_txt_result(file_path),
        EXT_CSV: lambda: _process_uploaded_csv_result(file_path),
        EXT_PNG: lambda: _convert_extraction_tuple_to_result(_process_image(file_path)),
        EXT_JPG: lambda: _convert_extraction_tuple_to_result(_process_image(file_path)),
        EXT_JPEG: lambda: _convert_extraction_tuple_to_result(_process_image(file_path)),
    }

    processor = processors.get(ext)
    if processor is None:
        return ExtractionResult.fail("Unsupported file type")

    return processor()


def _get_upload_extension(uploaded_file):
    return os.path.splitext(uploaded_file.name)[1].lower()


def _cleanup_temp_upload(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        logger.exception("Failed to delete temporary upload file.")


def _process_stored_upload(ext, file_path, uploaded_file) -> ExtractionResult:
    """Process stored upload. Returns ExtractionResult."""
    try:
        extraction_result = _dispatch_upload_processing(ext, file_path, uploaded_file)
        if extraction_result.success:
            return extraction_result
        raise UploadExtractionError(extraction_result.error or "Failed to process uploaded file")
    except UploadValidationError as exc:
        logger.warning("Validation error during stored upload processing: %s", exc)
        raise
    except UploadExtractionError as exc:
        logger.warning("Extraction error during stored upload processing: %s", exc)
        raise


def process_upload(uploaded_file):
    """
    Process uploaded file (boundary layer). Returns legacy tuple format for backward compatibility.
    
    Internal flow uses result objects (ValidationResult, ExtractionResult) for consistency.
    Exception handling maps domain errors back to tuple format.
    
    Returns: (success: bool, error: str | None, _unused: None, extracted_data: dict | None)
    """
    file_path = None
    try:
        # Validation phase (internal: ValidationResult)
        validation_is_valid, validation_error = validate_file(uploaded_file)
        validation_result = ValidationResult(
            is_valid=validation_is_valid,
            error=validation_error,
        )
        if not validation_result.is_valid:
            raise UploadValidationError(validation_result.error)

        # Storage phase (raises UploadStorageError)
        ext = _get_upload_extension(uploaded_file)
        try:
            file_path = save_temp_file(uploaded_file)
        except ValueError as exc:
            raise UploadStorageError(str(exc)) from exc

        # Extraction phase (internal: ExtractionResult)
        extraction_result = _process_stored_upload(ext, file_path, uploaded_file)
        
        # Convert result object to legacy tuple at boundary
        return True, None, None, extraction_result.extracted_data

    except UploadValidationError as exc:
        logger.warning(f"Validation error during upload: {exc}")
        return False, str(exc), None, None
    except UploadExtractionError as exc:
        logger.warning(f"Extraction error during upload: {exc}")
        return False, str(exc), None, None
    except UploadStorageError as exc:
        logger.warning(f"Storage error during upload: {exc}")
        return False, str(exc), None, None
    finally:
        if file_path:
            _cleanup_temp_upload(file_path)


def _validate_file_content(uploaded_file, ext) -> ValidationResult:
    """Validate file size, MIME type, and type-specific constraints."""
    return file_validation_service._validate_file_content(
        uploaded_file,
        ext,
        validate_image_func=validate_image,
        validate_mime_type_func=validate_mime_type,
        validate_excel_sheet_count_func=validate_excel_sheet_count,
        validate_word_func=word_validation_service.validate_word,
    )


def validate_file_result(uploaded_file) -> ValidationResult:
    """Validate uploaded file and return ValidationResult."""
    return file_validation_service.validate_file_result(
        uploaded_file,
        validate_image_func=validate_image,
        validate_mime_type_func=validate_mime_type,
        validate_excel_sheet_count_func=validate_excel_sheet_count,
        validate_word_func=word_validation_service.validate_word,
    )


def validate_pdf_result(uploaded_file) -> ValidationResult:
    return pdf_validation_service.validate_pdf_result(uploaded_file, reader_cls=PdfReader)


def check_pdf_encrypted(reader):
    return pdf_validation_service.check_pdf_encrypted(reader)


def check_pdf_structure(reader):
    return pdf_validation_service.check_pdf_structure(reader)


def check_pdf_page_count(page_count):
    return pdf_validation_service.check_pdf_page_count(page_count)


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
    return excel_validation_service.check_excel_sheet_count(sheet_count)


def _should_parse_as_xls(uploaded_file, ext):
    return excel_validation_service._should_parse_as_xls(
        uploaded_file,
        ext,
        is_ole_container_func=_is_ole_container,
        is_legacy_xls_content_func=_is_legacy_xls_content,
    )


def _get_xlsx_sheet_count(uploaded_file):
    return excel_validation_service._get_xlsx_sheet_count(uploaded_file)


def _get_xls_sheet_count(uploaded_file):
    return excel_validation_service._get_xls_sheet_count(uploaded_file)


def _validate_xlsx_mime_structure(uploaded_file):
    return mime_validation_service._validate_xlsx_mime_structure(
        uploaded_file,
        is_ole_container_func=_is_ole_container,
        is_legacy_xls_content_func=_is_legacy_xls_content,
        has_zip_signature_func=_has_zip_signature,
    )


def _validate_word_mime_structure(uploaded_file, ext):
    return mime_validation_service._validate_word_mime_structure(
        uploaded_file,
        ext,
        is_ole_container_func=_is_ole_container,
        has_zip_signature_func=_has_zip_signature,
    )


def _resolve_txt_detected_mime(uploaded_file, detected_mime):
    return mime_validation_service._resolve_txt_detected_mime(
        uploaded_file,
        detected_mime,
    )


def validate_mime_type(uploaded_file, ext):
    return mime_validation_service.validate_mime_type(
        uploaded_file,
        ext,
        allowed_mime_types=ALLOWED_MIME_TYPES,
        magic_module=magic,
        is_ole_container_func=_is_ole_container,
        is_legacy_xls_content_func=_is_legacy_xls_content,
        has_zip_signature_func=_has_zip_signature,
        has_binary_signature_func=_has_binary_signature,
    )


def _read_head(uploaded_file, size=2048):
    return mime_validation_service._read_head(uploaded_file, size)


def _detect_mime(head, ext):
    return mime_validation_service._detect_mime(head, ext, magic_module=magic)


def _fallback_mime(head, ext):
    return mime_validation_service._fallback_mime(head, ext)


def _is_ole_container(uploaded_file):
    return mime_validation_service._is_ole_container(uploaded_file)


def _is_legacy_xls_content(uploaded_file):
    return mime_validation_service._is_legacy_xls_content(uploaded_file)


def _has_zip_signature(uploaded_file):
    return mime_validation_service._has_zip_signature(uploaded_file)


def _has_binary_signature(uploaded_file):
    return mime_validation_service._has_binary_signature(uploaded_file)


def _validate_txt_content(uploaded_file, detected_mime: str):
    return mime_validation_service._validate_txt_content(
        uploaded_file,
        detected_mime,
        allowed_mime_types=ALLOWED_MIME_TYPES,
        has_binary_signature_func=_has_binary_signature,
    )


def _validate_csv_content(uploaded_file, detected_mime: str):
    return mime_validation_service._validate_csv_content(
        uploaded_file,
        detected_mime,
        allowed_mime_types=ALLOWED_MIME_TYPES,
        has_binary_signature_func=_has_binary_signature,
    )


def save_temp_file(uploaded_file):
    """Save uploaded file to temporary directory. Raises UploadStorageError on failure."""
    try:
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
    except ValueError:
        raise
    except UploadStorageError:
        raise
    except Exception as exc:
        logger.exception("Failed to save temporary upload file")
        raise UploadStorageError("Failed to save temporary file") from exc

# =============================================================================
# Test compatibility wrappers (backward compatibility for existing tests)
# These convert result objects back to tuple format for test infrastructure.
# Production code should use the result objects and process_upload as boundary.
# =============================================================================

def validate_file(uploaded_file):
    """Test compatibility wrapper: convert ValidationResult to tuple."""
    return validate_file_result(uploaded_file).to_legacy_tuple()


def validate_pdf(uploaded_file):
    """Test compatibility wrapper: convert ValidationResult to tuple."""
    return validate_pdf_result(uploaded_file).to_legacy_tuple()


def process_word(file_path, ext):
    """Test compatibility wrapper: convert ExtractionResult to tuple."""
    return _process_word_result(file_path, ext).to_legacy_tuple()


def _process_image(file_path):
    """Test compatibility wrapper: convert ExtractionResult to tuple."""
    return _process_image_result(file_path).to_legacy_tuple()
