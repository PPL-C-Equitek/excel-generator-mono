import os
import magic
from uuid import uuid4
from django.conf import settings
from django.utils.text import get_valid_filename
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

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

def process_upload(uploaded_file):
    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return False, error, None

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    is_valid, error = validate_mime_type(uploaded_file, ext)
    if not is_valid:
        return False, error, None

    if ext == ".pdf":

        is_valid, error = validate_pdf_not_corrupt(uploaded_file)
        if not is_valid:
            return False, error, None

        is_valid, error = validate_pdf_not_password_protected(uploaded_file)
        if not is_valid:
            return False, error, None

    file_path = save_temp_file(uploaded_file)

    return True, None, file_path


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
        header = uploaded_file.read(5)

        if not header.startswith(b"%PDF"):
            return False, "The file does not have a valid PDF header."

        return True, None

    except PdfReadError:
        return False, "The PDF file is corrupt."


def validate_pdf_not_password_protected(uploaded_file):
    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)

        if reader.is_encrypted:
            return False, "The PDF file is password-protected."

        return True, None

    except (Exception):
        return False, "The PDF file is password-protected and cannot be accessed"
    

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
