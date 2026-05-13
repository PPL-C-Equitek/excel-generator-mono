"""Shared file-type metadata for upload validation and extraction."""

from file_processing.services import word_validation_service

EXT_XLSX = ".xlsx"
EXT_XLS = ".xls"
EXT_PDF = ".pdf"
EXT_DOCX = ".docx"
EXT_DOC = ".doc"
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
MAX_WORD_PAGES = word_validation_service.MAX_WORD_PAGES

PDF_CORRUPT_ERROR = "PDF file is corrupt or has an invalid structure."
EXCEL_CORRUPT_ERROR = "Invalid or corrupted Excel file."
EXCEL_TOO_MANY_SHEETS_ERROR = f"Excel has too many sheets (maximum {MAX_EXCEL_SHEETS})."
EXCEL_PASSWORD_PROTECTED_ERROR = (
    "Excel file is password-protected. Please remove the password and try again."
)
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
DOES_NOT_MATCH_EXTENSION_ERROR = "File content does not match its extension."
UNSUPPORTED_FILE_TYPE_ERROR = (
    "Unsupported file type. Only PDF, XLS, XLSX, TXT, CSV, PNG, JPG, JPEG, "
    "DOC, and DOCX are allowed."
)

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

