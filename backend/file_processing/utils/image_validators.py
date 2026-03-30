"""
Low-level, single-responsibility image validators.

Each function accepts a Django ``UploadedFile`` and returns
``(is_valid: bool, error_message: str | None)``.
"""

import os
import logging

from PIL import Image

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic-number signatures
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPG_MAGIC = b"\xFF\xD8\xFF"


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


def validate_image_magic_number(uploaded_file):
    """Verify the file header matches known image magic numbers."""
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(8)

        if header.startswith(PNG_MAGIC):
            return True, None
        if header.startswith(JPG_MAGIC):
            return True, None

        return False, "File header does not match a supported image format."
    except Exception:
        logger.exception("Error reading file header for magic number check.")
        return False, "Unable to read file header."
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass


def validate_image_integrity(uploaded_file):
    """Use Pillow to verify the image data is not corrupted."""
    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        img.verify()  # raises if data is corrupt
        uploaded_file.seek(0)
        return True, None
    except Exception:
        uploaded_file.seek(0)
        return False, "Image file is corrupted or unreadable."
