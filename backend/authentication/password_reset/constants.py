from __future__ import annotations

from datetime import timedelta

from authentication.services import (
    PASSWORD_RESET_RESEND_SUCCESS_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
)

PASSWORD_RESET_REQUEST_SUCCESS_MESSAGE = PASSWORD_RESET_SUCCESS_MESSAGE
PASSWORD_RESET_RESEND_REQUEST_SUCCESS_MESSAGE = (
    PASSWORD_RESET_RESEND_SUCCESS_MESSAGE
)
PASSWORD_RESET_COMPLETED_MESSAGE = "Password reset successfully"
PASSWORD_RESET_INVALID_TOKEN_MESSAGE = "Invalid token"
PASSWORD_RESET_EXPIRED_TOKEN_MESSAGE = (
    "Token expired. Please request a new password reset email."
)
PASSWORD_RESET_USER_NOT_FOUND_MESSAGE = "User not found"
PASSWORD_RESET_SERVER_ERROR_MESSAGE = (
    "An internal server error occurred. Please try again later."
)
PASSWORD_RESET_TOKEN_MAX_AGE = timedelta(hours=1)
