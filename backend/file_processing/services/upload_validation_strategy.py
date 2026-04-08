from dataclasses import dataclass
from typing import Any, Protocol


ValidationResult = tuple[bool, str | None]


class FileValidationStrategy(Protocol):
    def validate(self, uploaded_file: Any, ext: str) -> ValidationResult: ...


@dataclass
class WordValidationStrategy:
    word_validation_service: Any
    supported_extensions: set[str]

    def validate(self, uploaded_file: Any, ext: str) -> ValidationResult:
        if ext not in self.supported_extensions:
            return True, None
        return self.word_validation_service.validate_word(uploaded_file, ext)
