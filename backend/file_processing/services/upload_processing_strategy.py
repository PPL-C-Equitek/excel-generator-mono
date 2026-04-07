from __future__ import annotations

from typing import Callable

ProcessingResult = tuple[bool, str | None, object | None]


class UploadProcessingStrategy:
    """Base strategy for file-specific processing."""

    def process(self) -> ProcessingResult:
        raise NotImplementedError


class CallableUploadProcessingStrategy(UploadProcessingStrategy):
    """Adapter strategy that wraps a callable processor."""

    def __init__(self, processor: Callable[[], ProcessingResult]):
        self._processor = processor

    def process(self) -> ProcessingResult:
        return self._processor()


class UploadProcessingStrategyRegistry:
    """Registry that maps file extensions to concrete strategies."""

    def __init__(self):
        self._strategies: dict[str, UploadProcessingStrategy] = {}

    def register(self, extensions: list[str], strategy: UploadProcessingStrategy) -> None:
        for extension in extensions:
            self._strategies[extension] = strategy

    def resolve(self, extension: str) -> UploadProcessingStrategy | None:
        return self._strategies.get(extension)
