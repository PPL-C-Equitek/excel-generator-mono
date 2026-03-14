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


def deskew_image(image_array: np.ndarray) -> np.ndarray:
    """Detect and correct small rotation (skew) in the image.

    Uses the minimum-area bounding rectangle of non-zero pixels to
    estimate skew angle.  Only corrects angles within ±15° to avoid
    rotating correctly-oriented images.
    """
    coords = np.column_stack(np.where(image_array > 0))
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
    1. Convert to grayscale
    2. Normalize contrast (CLAHE)
    3. Remove noise (median blur)
    4. Apply Otsu thresholding
    5. Deskew

    Returns a preprocessed PIL Image suitable for OCR.
    """
    image_array = np.array(pil_image)

    image_array = convert_to_grayscale(image_array)
    image_array = normalize_contrast(image_array)
    image_array = remove_noise(image_array)
    image_array = apply_thresholding(image_array)
    image_array = deskew_image(image_array)

    return Image.fromarray(image_array)
