class DuplicateEmailError(Exception):
    """Raised when attempting to create a user with an email that already exists."""
    pass
