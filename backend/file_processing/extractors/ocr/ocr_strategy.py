"""Document-type OCR cleanup strategies.

The cleanup implementation stays deterministic and backend-only. These
strategies provide the documented public API and route documents to the
shared cleanup service with the right document type metadata.
"""

from __future__ import annotations

from typing import Any

from file_processing.services.ocr_cleanup_service import OCRCleanupService


class OCRCleanupOrchestrator:
    @staticmethod
    def to_llm_context(cleanup_result: dict[str, Any]) -> dict[str, Any]:
        return dict(cleanup_result.get("ocr_metadata", {}))


class _BaseOCRStrategy:
    document_type = "unknown"

    def __init__(self, cleanup_service: OCRCleanupService | None = None):
        self.cleanup_service = cleanup_service or OCRCleanupService()

    def cleanup_text(
        self,
        text: str,
        word_details: Any | None = None,
        avg_confidence: float = 0.0,
        schema_definitions: Any | None = None,
    ) -> dict[str, Any]:
        return self.cleanup_service.cleanup_text(
            text=text,
            avg_confidence=avg_confidence,
            word_details=word_details,
            schema_definitions=schema_definitions,
            document_type=self.document_type,
        )


class PDFOCRStrategy(_BaseOCRStrategy):
    document_type = "pdf"


class ImageOCRStrategy(_BaseOCRStrategy):
    document_type = "image"


class ScannedExcelOCRStrategy(_BaseOCRStrategy):
    document_type = "scanned_excel"


class OCRStrategyFactory:
    _STRATEGIES = {
        "pdf": PDFOCRStrategy,
        "image": ImageOCRStrategy,
        "scanned_excel": ScannedExcelOCRStrategy,
    }

    @classmethod
    def get_strategy(cls, document_type: str | None) -> _BaseOCRStrategy:
        normalized = (document_type or "unknown").strip().lower()
        strategy_class = cls._STRATEGIES.get(normalized, _BaseOCRStrategy)
        return strategy_class()

    @classmethod
    def cleanup_text_for_document(
        cls,
        document_type: str,
        text: str,
        word_details: Any | None = None,
        avg_confidence: float = 0.0,
        schema_definitions: Any | None = None,
    ) -> dict[str, Any]:
        strategy = cls.get_strategy(document_type)
        return strategy.cleanup_text(
            text=text,
            word_details=word_details,
            avg_confidence=avg_confidence,
            schema_definitions=schema_definitions,
        )
