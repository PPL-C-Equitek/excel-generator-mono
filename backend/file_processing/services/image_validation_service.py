"""
Image validation service — orchestrates all image-specific validation.

MIME validation is handled inline using ``python-magic`` (same library
used by upload_service) to avoid circular imports while keeping the
same validation contract.
"""

import os
import logging
import magic

from file_processing.utils.image_validators import (
    validate_image_extension,
    validate_image_size,
    validate_image_magic_number,
    validate_image_integrity,
)

logger = logging.getLogger(__name__)

# MIME types accepted for each image extension
IMAGE_MIME_TYPES = {
    ".png": [
        "image/png",
        "image/x-png",
        "application/png",
        "application/x-png",
    ],
    ".jpg": [
        "image/jpeg",
        "image/pjpeg",
        "image/x-citrix-jpeg",
    ],
    ".jpeg": [
        "image/jpeg",
        "image/pjpeg",
        "image/x-citrix-jpeg",
    ],
}


def validate_image(uploaded_file):
    """
    Run all image validations in order and short-circuit on the first failure.

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    # 1. Extension
    is_valid, err = validate_image_extension(uploaded_file)
    if not is_valid:
        return False, err

    # 2. Size
    is_valid, err = validate_image_size(uploaded_file)
    if not is_valid:
        return False, err

    # 3. MIME
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    is_valid, err = validate_image_mime_type(uploaded_file, ext)
    if not is_valid:
        return False, err

    # 4. Magic number
    is_valid, err = validate_image_magic_number(uploaded_file)
    if not is_valid:
        return False, err

    # 5. Integrity (Pillow)
    is_valid, err = validate_image_integrity(uploaded_file)
    if not is_valid:
        return False, err

    return True, None


def validate_image_mime_type(uploaded_file, ext):
    """
    Validate MIME type for image files using python-magic.

    Same approach as upload_service.validate_mime_type() but with
    image-specific allowed MIME types, avoiding a circular import.
    """
    try:
        uploaded_file.seek(0)
        mime = magic.from_buffer(uploaded_file.read(2048), mime=True)

        expected = IMAGE_MIME_TYPES.get(ext, [])
        if mime not in expected:
            return False, "File content does not match its extension."

        return True, None
    except Exception:
        logger.exception("Error validating image MIME type.")
        return False, "Unable to determine file type."
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            logger.exception("Error resetting file pointer after MIME validation.")
