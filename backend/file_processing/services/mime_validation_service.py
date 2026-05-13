"""MIME and signature validation helpers for uploaded files."""

from file_processing.services.upload_file_types import (
    ALLOWED_MIME_TYPES,
    BINARY_SIGNATURES,
    CSV_CORRUPT_ERROR,
    CSV_PROTECTED_ERROR,
    DOES_NOT_MATCH_EXTENSION_ERROR,
    EXT_CSV,
    EXT_DOC,
    EXT_DOCX,
    EXT_TXT,
    EXT_XLS,
    EXT_XLSX,
    EXCEL_PASSWORD_PROTECTED_ERROR,
    MIME_OCTET_STREAM,
    MIME_OLE_STORAGE,
    MIME_TYPE_DETECTION_ERROR,
    MIME_ZIP,
    OLE_SIGNATURE,
    TXT_CORRUPT_ERROR,
    ZIP_SIGNATURE_PREFIX,
)

try:
    import magic
except Exception:  # pragma: no cover - optional dependency in local envs

    class _MagicShim:
        @staticmethod
        def from_buffer(_buffer, mime=True):
            raise ImportError("python-magic unavailable")

    magic = _MagicShim()


def validate_mime_type(
    uploaded_file,
    ext,
    *,
    allowed_mime_types=None,
    magic_module=None,
    is_ole_container_func=None,
    is_legacy_xls_content_func=None,
    has_zip_signature_func=None,
    has_binary_signature_func=None,
):
    try:
        allowed_mime_types = allowed_mime_types or ALLOWED_MIME_TYPES
        head = _read_head(uploaded_file)
        mime = _detect_mime(head, ext, magic_module=magic_module)

        if not mime:
            return False, MIME_TYPE_DETECTION_ERROR

        expected_mimes = allowed_mime_types.get(ext, [])

        if ext == EXT_XLSX:
            xlsx_state, xlsx_error = _validate_xlsx_mime_structure(
                uploaded_file,
                is_ole_container_func=is_ole_container_func,
                is_legacy_xls_content_func=is_legacy_xls_content_func,
                has_zip_signature_func=has_zip_signature_func,
            )
            if xlsx_state == "legacy":
                return True, None
            if xlsx_error:
                return False, xlsx_error

        if ext == EXT_TXT:
            detected_mime = _resolve_txt_detected_mime(uploaded_file, mime)
            return _validate_txt_content(
                uploaded_file,
                detected_mime,
                allowed_mime_types=allowed_mime_types,
                has_binary_signature_func=has_binary_signature_func,
            )

        if ext == EXT_CSV:
            return _validate_csv_content(
                uploaded_file,
                mime,
                allowed_mime_types=allowed_mime_types,
                has_binary_signature_func=has_binary_signature_func,
            )

        if ext in {EXT_DOC, EXT_DOCX}:
            word_error = _validate_word_mime_structure(
                uploaded_file,
                ext,
                is_ole_container_func=is_ole_container_func,
                has_zip_signature_func=has_zip_signature_func,
            )
            if word_error:
                return False, word_error

        if mime not in expected_mimes:
            return False, DOES_NOT_MATCH_EXTENSION_ERROR

        return True, None

    except Exception:
        return False, MIME_TYPE_DETECTION_ERROR


def _read_head(uploaded_file, size=2048):
    uploaded_file.seek(0)
    head = uploaded_file.read(size)
    uploaded_file.seek(0)
    return head


def _detect_mime(head, ext, *, magic_module=None):
    magic_module = magic_module or magic
    try:
        return magic_module.from_buffer(head, mime=True)
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


def _is_ole_container(uploaded_file):
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(len(OLE_SIGNATURE))
        uploaded_file.seek(0)
        return header == OLE_SIGNATURE
    except Exception:
        return False


def _is_legacy_xls_content(uploaded_file):
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


def _validate_xlsx_mime_structure(
    uploaded_file,
    *,
    is_ole_container_func=None,
    is_legacy_xls_content_func=None,
    has_zip_signature_func=None,
):
    is_ole_container_func = is_ole_container_func or _is_ole_container
    is_legacy_xls_content_func = (
        is_legacy_xls_content_func or _is_legacy_xls_content
    )
    has_zip_signature_func = has_zip_signature_func or _has_zip_signature

    if is_ole_container_func(uploaded_file):
        if is_legacy_xls_content_func(uploaded_file):
            return "legacy", None
        return "invalid", EXCEL_PASSWORD_PROTECTED_ERROR

    if not has_zip_signature_func(uploaded_file):
        return "invalid", DOES_NOT_MATCH_EXTENSION_ERROR

    return "valid", None


def _validate_word_mime_structure(
    uploaded_file,
    ext,
    *,
    is_ole_container_func=None,
    has_zip_signature_func=None,
):
    is_ole_container_func = is_ole_container_func or _is_ole_container
    has_zip_signature_func = has_zip_signature_func or _has_zip_signature

    if ext == EXT_DOC and not is_ole_container_func(uploaded_file):
        return DOES_NOT_MATCH_EXTENSION_ERROR

    if ext == EXT_DOCX:
        # Encrypted OOXML (.docx) is wrapped in an OLE container; allow it to
        # continue to Word validation so it can return the protected-file error.
        if is_ole_container_func(uploaded_file):
            return None
        if not has_zip_signature_func(uploaded_file):
            return DOES_NOT_MATCH_EXTENSION_ERROR

    return None


def _resolve_txt_detected_mime(uploaded_file, detected_mime):
    request_mime = (getattr(uploaded_file, "content_type", "") or "").lower()
    if (
        detected_mime in {MIME_OCTET_STREAM, MIME_ZIP, MIME_OLE_STORAGE}
        and request_mime
    ):
        return request_mime
    return detected_mime


def _validate_txt_content(
    uploaded_file,
    detected_mime: str,
    *,
    allowed_mime_types=None,
    has_binary_signature_func=None,
):
    allowed_mime_types = allowed_mime_types or ALLOWED_MIME_TYPES
    has_binary_signature_func = has_binary_signature_func or _has_binary_signature
    is_binary, binary_error = has_binary_signature_func(uploaded_file)
    if is_binary:
        return False, binary_error

    if detected_mime and detected_mime.startswith("text/"):
        return True, None

    allowed = allowed_mime_types.get(EXT_TXT, [])
    if detected_mime in allowed:
        return True, None

    return False, TXT_CORRUPT_ERROR


def _validate_csv_content(
    uploaded_file,
    detected_mime: str,
    *,
    allowed_mime_types=None,
    has_binary_signature_func=None,
):
    allowed_mime_types = allowed_mime_types or ALLOWED_MIME_TYPES
    has_binary_signature_func = has_binary_signature_func or _has_binary_signature
    is_binary, binary_error = has_binary_signature_func(uploaded_file)
    if is_binary:
        uploaded_file.seek(0)
        header = uploaded_file.read(8)
        uploaded_file.seek(0)
        if header == OLE_SIGNATURE:
            return False, CSV_PROTECTED_ERROR
        return False, binary_error

    if detected_mime and detected_mime.startswith("text/"):
        return True, None

    allowed = allowed_mime_types.get(EXT_CSV, [])
    if detected_mime in allowed:
        return True, None

    return False, CSV_CORRUPT_ERROR
