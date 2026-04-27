"""Domain exception hierarchy for auth-system.

These exceptions are raised by the data and token-utility layers.
They are converted to HTTP responses by global handlers registered
in `app.api.exception_handlers`. Services should generally NOT catch
them — let them propagate. Three documented carve-outs exist; see the
slice 1 design doc for details.
"""


class DomainError(Exception):
    """Base for all domain-level exceptions. Never raised directly."""


class DuplicateEmailError(DomainError):
    """Raised when attempting to create a user with an email that already exists."""


class DuplicateOAuthAccountError(DomainError):
    """Raised when attempting to link an OAuth account already linked elsewhere."""


class TokenError(DomainError):
    """Base for JWT decode/validation failures."""


class InvalidTokenError(TokenError):
    """Token signature invalid, malformed, or otherwise un-decodable."""


class ExpiredTokenError(TokenError):
    """Token signature is valid but the `exp` claim has passed."""


class WrongTokenTypeError(TokenError):
    """Token decoded successfully but its `type` claim is not what was expected."""
