from __future__ import annotations


class ChangePasswordServiceError(Exception):
    pass


class CurrentPasswordRequiredError(Exception):
    pass


class InvalidCurrentPasswordError(Exception):
    pass


class PasswordReuseError(Exception):
    pass
