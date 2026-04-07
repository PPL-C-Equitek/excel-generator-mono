"""
Centralized OCR configuration.

All OCR-related settings are defined here so they can be tuned in one place.
"""

import os

# Tesseract settings
# OEM 3 = Default, uses whatever is available (Legacy + LSTM).
TESSERACT_OEM = 3
# PSM modes used in the multi-pass strategy (tried in order; best result wins).
# PSM 3 = Fully automatic page segmentation (good for mixed/complex layouts).
# PSM 6 = Assume a single uniform block of text (good for clean documents).
# PSM 4 = Assume a single column of text (good for single-column scans).
TESSERACT_PSM_MODES = [3, 6, 4]
# Legacy single PSM for backward-compatibility.
TESSERACT_PSM = 3
# Language model (env override supported).
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng+ind")


def get_tesseract_lang() -> str:
    """Return current Tesseract language setting."""
    return os.getenv("TESSERACT_LANG", TESSERACT_LANG)

def get_tesseract_config(psm: int | None = None):
    """Return Tesseract CLI config string built from the settings above."""
    mode = psm if psm is not None else TESSERACT_PSM
    return f"--oem {TESSERACT_OEM} --psm {mode}"

# EasyOCR settings
# Languages supported by EasyOCR (list of language codes).
EASYOCR_LANGUAGES = ["en", "id"]
# Whether to use GPU acceleration (requires CUDA).  Set False for CPU-only.
EASYOCR_GPU = False
# Fraction of average text height used as the Y-distance threshold for
# grouping EasyOCR text regions into visual lines.  Two regions whose
# vertical midpoints are closer than (avg_height × this value) are
# considered part of the same line.  0.6 works well for most financial
# documents (invoices, receipts, statements).
EASYOCR_LINE_Y_THRESHOLD = 0.6

# PDF-to-image conversion
# DPI for converting PDF pages to images.
# 400 DPI provides better character resolution for OCR on scanned documents.
PDF_TO_IMAGE_DPI = 400

# Image preprocessing
# Median blur kernel size for noise removal.
NOISE_REMOVAL_KERNEL_SIZE = 3

# CLAHE parameters for contrast normalization.
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)

# Upscale images whose height is below this threshold (pixels).
UPSCALE_MIN_HEIGHT = 1500
# Scaling factor applied to small images.
UPSCALE_FACTOR = 2.0

# White border padding (pixels) added around the image so text doesn't
# touch the edges — Tesseract needs some breathing room.
BORDER_PADDING_PX = 20

# Kernel size for morphological closing (reconnects broken strokes).
MORPH_KERNEL_SIZE = 2

# Confidence / pipeline thresholds
# Minimum average EasyOCR confidence (0-100 scale) before falling back
# to Tesseract.  EasyOCR is the primary engine; if its confidence drops
# below this threshold, Tesseract (with heavy preprocessing) is tried as
# a last resort for very noisy or low-contrast scans.
CONFIDENCE_THRESHOLD = 40.0

# Minimum average characters per page from PyPDF2 text extraction before
# treating the PDF as "scanned" and switching to OCR.
TEXT_LAYER_MIN_CHARS_PER_PAGE = 50

# Standalone image OCR preprocessing
IMAGE_OCR_APPLY_THRESHOLD = True
IMAGE_OCR_THRESHOLD = 180
