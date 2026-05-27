"""
Abstract base class for all OCR engines.

Every OCR engine must implement ``extract_text()``.  Engines that can
report confidence should also override ``extract_text_with_confidence()``.
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple

class BaseOCREngine(ABC):
    """Interface that all OCR engine implementations must satisfy."""

    @abstractmethod
    def extract_text(self, image: Any) -> str:
        """Extract text from *image* and return it as a string."""
        raise NotImplementedError

    def extract_text_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Extract text and return ``(text, confidence)``.

        *confidence* is a float in [0, 100].  The default implementation
        delegates to ``extract_text()`` and returns ``0.0`` as confidence
        so callers know that the engine does not provide a real score.
        """
        return self.extract_text(image), 0.0

    def extract_text_with_metadata(self, image: Any) -> dict[str, Any]:
        """Extract OCR text plus optional confidence metadata.

        Engines that can provide layout-aware word details should override this
        method. The default implementation preserves backwards compatibility by
        delegating to ``extract_text_with_confidence()`` and returning an empty
        ``word_details`` list.
        """
        text, confidence = self.extract_text_with_confidence(image)
        return {
            "text": text,
            "avg_confidence": confidence,
            "word_details": [],
        }
