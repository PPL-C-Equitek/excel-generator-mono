"""Factories for bundling OCR engines with image preprocessors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from file_processing.extractors.image_preprocessors import (
    BaseImagePreprocessor,
    GrayscaleThresholdPreprocessor,
)
from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine


class BaseOcrBundleFactory(ABC):
    """Abstract factory for OCR engine + preprocessor bundles."""

    @abstractmethod
    def create_engine(self) -> BaseOCREngine:
        raise NotImplementedError

    @abstractmethod
    def create_preprocessor(self) -> BaseImagePreprocessor:
        raise NotImplementedError


class DefaultOcrFactory(BaseOcrBundleFactory):
    """Default OCR bundle used by ImageExtractor."""

    def create_engine(self) -> BaseOCREngine:
        return TesseractEngine(apply_preprocessing=False)

    def create_preprocessor(self) -> BaseImagePreprocessor:
        return GrayscaleThresholdPreprocessor()
