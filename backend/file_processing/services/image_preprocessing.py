"""
Image preprocessing helpers for OCR accuracy improvement.

Each function performs a single, well-defined operation on an image.
The main entry point is ``preprocess_image()``, which chains them into
a full pipeline and returns a PIL Image ready for OCR.

Why preprocessing matters:
- Grayscale conversion removes color noise that confuses OCR engines.
- Noise removal (median blur) eliminates speckling from scanner artefacts.
- Thresholding (Otsu) converts the image to pure black-and-white, giving
  the OCR engine crisp character boundaries.
- Contrast normalization (CLAHE) rescues text in unevenly-lit scans.
- Deskewing straightens rotated pages so line segmentation works properly.
"""

import numpy as np
import cv2
from PIL import Image

from file_processing.services.ocr_config import (
    CLAHE_CLIP_LIMIT,
    CLAHE_TILE_GRID_SIZE,
    NOISE_REMOVAL_KERNEL_SIZE,
    UPSCALE_MIN_HEIGHT,
    UPSCALE_FACTOR,
    BORDER_PADDING_PX,
    MORPH_KERNEL_SIZE,
)

def convert_to_grayscale(image_array: np.ndarray) -> np.ndarray:
    """Convert a BGR or RGB image to single-channel grayscale.

    If the image is already single-channel it is returned unchanged.
    """
    if len(image_array.shape) == 2:
        return image_array
    return cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)


def remove_noise(image_array: np.ndarray) -> np.ndarray:
    """Apply median blur to remove salt-and-pepper noise from scans."""
    return cv2.medianBlur(image_array, NOISE_REMOVAL_KERNEL_SIZE)


def apply_thresholding(image_array: np.ndarray) -> np.ndarray:
    """Binarize the image using Otsu's thresholding.

    Otsu automatically picks the optimal threshold separating foreground
    (text) from background, which works well for most scanned documents.
    """
    _, thresholded = cv2.threshold(
        image_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    return thresholded


def normalize_contrast(image_array: np.ndarray) -> np.ndarray:
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization).

    CLAHE improves local contrast, which is especially helpful for scans
    with shadows, creases, or uneven lighting.
    """
    clahe = cv2.createCLAHE(
        clipLimit=CLAHE_CLIP_LIMIT,
        tileGridSize=CLAHE_TILE_GRID_SIZE,
    )
    return clahe.apply(image_array)


def upscale_image(image_array: np.ndarray) -> np.ndarray:
    """Upscale small images so OCR engines have enough pixel data.

    Images shorter than ``UPSCALE_MIN_HEIGHT`` are scaled up by
    ``UPSCALE_FACTOR`` using bicubic interpolation.  This dramatically
    improves recognition of small or low-resolution text.
    """
    h, w = image_array.shape[:2]
    if h < UPSCALE_MIN_HEIGHT:
        new_w = int(w * UPSCALE_FACTOR)
        new_h = int(h * UPSCALE_FACTOR)
        return cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    return image_array


def add_border_padding(image_array: np.ndarray) -> np.ndarray:
    """Add white border padding around the image.

    Tesseract performs poorly when text touches the image edges.
    A small border gives the engine room to detect character boundaries.
    """
    pad = BORDER_PADDING_PX
    return cv2.copyMakeBorder(
        image_array, pad, pad, pad, pad,
        cv2.BORDER_CONSTANT, value=255,
    )


def apply_adaptive_thresholding(image_array: np.ndarray) -> np.ndarray:
    """Binarize using adaptive Gaussian thresholding.

    Unlike global Otsu, adaptive thresholding calculates a separate
    threshold for each local region, handling uneven lighting, shadows,
    and creases much better — common issues in scanned documents.
    """
    return cv2.adaptiveThreshold(
        image_array, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )


def morphological_cleanup(image_array: np.ndarray) -> np.ndarray:
    """Apply morphological closing to reconnect broken character strokes.

    Scanning artefacts and aggressive thresholding can break thin strokes
    (e.g. the crossbar on 'e', serifs on 'i').  A small closing operation
    bridges tiny gaps without merging adjacent characters.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE),
    )
    return cv2.morphologyEx(image_array, cv2.MORPH_CLOSE, kernel)


def deskew_image(image_array: np.ndarray) -> np.ndarray:
    """Detect and correct small rotation (skew) in the image.

    Uses the minimum-area bounding rectangle of non-zero pixels to
    estimate skew angle.  Only corrects angles within ±15° to avoid
    rotating correctly-oriented images.
    """
    coords = np.column_stack(np.nonzero(image_array > 0))
    if coords.shape[0] < 10:
        # Not enough foreground pixels to estimate skew.
        return image_array

    angle = cv2.minAreaRect(coords)[-1]

    # minAreaRect returns angles in [-90, 0). Normalize to a small range.
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only correct small skew angles.
    if abs(angle) > 15 or abs(angle) < 0.5:
        return image_array

    h, w = image_array.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image_array, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """Run the complete preprocessing pipeline on a PIL Image.

    Steps:
    1. Upscale small images for better character resolution
    2. Convert to grayscale
    3. Normalize contrast (CLAHE)
    4. Remove noise (median blur)
    5. Apply adaptive thresholding (handles uneven lighting)
    6. Morphological closing (reconnect broken strokes)
    7. Deskew
    8. Add border padding

    Returns a preprocessed PIL Image suitable for OCR.
    """
    image_array = np.array(pil_image)

    image_array = upscale_image(image_array)
    image_array = convert_to_grayscale(image_array)
    image_array = normalize_contrast(image_array)
    image_array = remove_noise(image_array)
    image_array = apply_adaptive_thresholding(image_array)
    image_array = morphological_cleanup(image_array)
    image_array = deskew_image(image_array)
    image_array = add_border_padding(image_array)

    return Image.fromarray(image_array)
