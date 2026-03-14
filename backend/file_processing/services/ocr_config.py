"""
Centralized OCR configuration.

All OCR-related settings are defined here so they can be tuned in one place.
"""

# OEM 3 = Default, uses whatever is available (Legacy + LSTM).
TESSERACT_OEM = 3
# PSM 6 = Assume a single uniform block of text.
# Good for scanned documents with standard layouts.
TESSERACT_PSM = 6
# Language model — English + Indonesian
TESSERACT_LANG = "eng+ind"

def get_tesseract_config():
    """Return Tesseract CLI config string built from the settings above."""
    return f"--oem {TESSERACT_OEM} --psm {TESSERACT_PSM}"

# Languages supported by EasyOCR (list of language codes).
EASYOCR_LANGUAGES = ["en", "id"]
# Whether to use GPU acceleration (requires CUDA).  Set False for CPU-only.
EASYOCR_GPU = False

# DPI for converting PDF pages to images.
# 300 DPI: high enough for accurate OCR, not so high that it slows down processing significantly.
PDF_TO_IMAGE_DPI = 300

# Median blur kernel size for noise removal.
NOISE_REMOVAL_KERNEL_SIZE = 3

# CLAHE parameters for contrast normalization.
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)

# Minimum average Tesseract confidence (0-100 scale) before falling back
# to EasyOCR.  A value below this means Tesseract is struggling with the
# document (e.g. handwriting, poor scan quality).
CONFIDENCE_THRESHOLD = 40.0

# Minimum average characters per page from PyPDF2 text extraction before
# treating the PDF as "scanned" and switching to OCR.
TEXT_LAYER_MIN_CHARS_PER_PAGE = 50