"""Image preprocessing strategies used by image OCR extraction.

The image pipeline follows the Strategy pattern:
- the extractor depends on a preprocessor abstraction
- different preprocessing behaviors can be swapped without changing the
  extractor or upload orchestration
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image, ImageOps

from file_processing.services.ocr_config import (
    IMAGE_OCR_APPLY_THRESHOLD,
    IMAGE_OCR_THRESHOLD,
)


class BaseImagePreprocessor(ABC):
    """Strategy interface for image preprocessing before OCR."""

    @abstractmethod
    def preprocess(self, image: Image.Image) -> Image.Image:
        raise NotImplementedError


class GrayscaleThresholdPreprocessor(BaseImagePreprocessor):
    """Convert to grayscale and optionally apply binary thresholding."""

    def __init__(self, *, apply_thresholding: bool = IMAGE_OCR_APPLY_THRESHOLD, threshold_value: int = IMAGE_OCR_THRESHOLD):
        self.apply_thresholding = apply_thresholding
        self.threshold_value = threshold_value

    def preprocess(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)

        if not self.apply_thresholding:
            return grayscale

        return grayscale.point(
            lambda pixel: 255 if pixel > self.threshold_value else 0,
            mode="1",
        )
