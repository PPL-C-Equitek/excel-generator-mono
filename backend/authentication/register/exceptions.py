class RegistrationServiceError(Exception):
    """Raised when the register application service encounters an unexpected error."""


class RegistrationConflictError(Exception):
    """Raised when registration cannot proceed because the email already exists."""


class UnverifiedRegistrationError(Exception):
    """Raised when an unverified email re-registers and verification is re-sent."""
