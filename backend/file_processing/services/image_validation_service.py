import os
import logging

from file_processing.utils.image_validators import (
    validate_image_extension,
    validate_image_size,
    validate_image_magic_number,
    validate_image_integrity,
)

from file_processing.services.upload_service import (
    validate_mime_type as validate_image_mime_type
)

logger = logging.getLogger(__name__)

def validate_image(uploaded_file):
    """
    Run all image validations in order and short-circuit on the first failure.
    """
    # 1. Extension
    is_valid, err = validate_image_extension(uploaded_file)
    if not is_valid:
        return False, err

    # 2. Size
    is_valid, err = validate_image_size(uploaded_file)
    if not is_valid:
        return False, err

    # 3. MIME type
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
