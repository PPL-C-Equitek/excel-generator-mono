import os
from uuid import uuid4
from django.conf import settings

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]


def validate_extension(uploaded_file):
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type. Only PDF, XLS, and XLSX are allowed."

    return True, None


def save_temp_file(uploaded_file):
    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)

    unique_name = f"{uuid4()}_{uploaded_file.name}"
    file_path = os.path.join(settings.UPLOAD_TEMP_DIR, unique_name)

    with open(file_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return file_path