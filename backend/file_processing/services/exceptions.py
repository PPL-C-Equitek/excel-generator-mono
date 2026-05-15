"""Domain exceptions for upload and extraction pipeline."""


class UploadPipelineError(Exception):
    """Base domain exception for upload pipeline failures."""


class UploadValidationError(UploadPipelineError):
    """Raised when uploaded input fails validation rules."""


class UploadExtractionError(UploadPipelineError):
    """Raised when extraction/processing fails after validation."""


class UploadStorageError(UploadPipelineError):
    """Raised when temporary upload storage operations fail."""
