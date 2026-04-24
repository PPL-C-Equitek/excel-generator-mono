class LoginServiceError(Exception):
    """Raised when login flow fails unexpectedly."""


class LoginRateLimitedError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass
