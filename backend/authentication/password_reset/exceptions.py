from __future__ import annotations


class PasswordResetServiceError(Exception):
    pass


class PasswordResetTokenExpiredError(Exception):
    pass


class InvalidPasswordResetTokenError(Exception):
    pass


class PasswordResetUserNotFoundError(Exception):
    pass
