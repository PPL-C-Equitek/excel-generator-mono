"""
Low-level, single-responsibility image validators.

Each function accepts a Django ``UploadedFile`` and returns
``(is_valid: bool, error_message: str | None)``.
"""

import os
import logging

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic-number prefixes
PNG_MAGIC = b"\x89PNG"
JPG_MAGIC = b"\xFF\xD8"


def validate_image_extension(uploaded_file):
    """Check that the file extension is a supported image type."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return False, (
            "Unsupported image type. Only PNG, JPG, and JPEG are allowed."
        )
    return True, None


def validate_image_size(uploaded_file):
    """Reject files larger than 10 MB."""
    if uploaded_file.size > MAX_IMAGE_SIZE:
        return False, "File too large. Maximum allowed size is 10MB."
    return True, None

