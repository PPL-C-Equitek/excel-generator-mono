"""
Shared file upload policy constants.

These are used across multiple modules (upload validation, image validation)
without pulling in heavy dependencies.
"""

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FILE_TOO_LARGE_ERROR = "File too large. Maximum allowed size is 10MB."
