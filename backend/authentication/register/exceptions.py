class RegistrationServiceError(Exception):
    """Raised when the register application service encounters an unexpected error."""


class RegistrationConflictError(Exception):
    """Raised when registration cannot proceed because the email already exists."""
