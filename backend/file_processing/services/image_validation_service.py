"""
Image validation service — orchestrates all image-specific validation.

MIME validation is handled inline using ``python-magic`` (same library
used by upload_service) to avoid circular imports while keeping the
same validation contract.
"""

import os
import logging

try:
    import magic
except Exception:  # pragma: no cover - optional dependency in local envs

    class _MagicShim:
        @staticmethod
        def from_buffer(_buffer, mime=True):
            raise ImportError("python-magic unavailable")

    magic = _MagicShim()

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

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"


def _resolve_image_mime_fallback(uploaded_file, ext):
    """
    Best-effort MIME fallback for environments without libmagic.
    """
    expected = IMAGE_MIME_TYPES.get(ext, [])
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type in expected:
        return content_type

    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(16)
    except Exception:
        return None

    if header.startswith(PNG_SIGNATURE):
        return "image/png"
    if header.startswith(JPEG_SIGNATURE):
        return "image/jpeg"

    return None


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
    mime = None

    try:
        uploaded_file.seek(0)
        mime = magic.from_buffer(uploaded_file.read(2048), mime=True)
    except Exception:
        logger.exception("Error validating image MIME type.")
        mime = _resolve_image_mime_fallback(uploaded_file, ext)
        if not mime:
            return False, "Unable to determine file type."
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            logger.exception("Error resetting file pointer after MIME validation.")

    expected = IMAGE_MIME_TYPES.get(ext, [])
    if mime not in expected:
        return False, "File content does not match its extension."

    return True, None
