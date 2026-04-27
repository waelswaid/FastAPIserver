"""Unit tests for the domain exception hierarchy."""
import pytest

from app.exceptions import (
    DomainError,
    DuplicateEmailError,
    DuplicateOAuthAccountError,
    TokenError,
    InvalidTokenError,
    ExpiredTokenError,
    WrongTokenTypeError,
)


def test_domain_error_is_base():
    assert issubclass(DuplicateEmailError, DomainError)
    assert issubclass(DuplicateOAuthAccountError, DomainError)
    assert issubclass(TokenError, DomainError)


def test_token_error_subclasses():
    assert issubclass(InvalidTokenError, TokenError)
    assert issubclass(ExpiredTokenError, TokenError)
    assert issubclass(WrongTokenTypeError, TokenError)


def test_exceptions_can_be_instantiated_with_message():
    assert str(InvalidTokenError("boom")) == "boom"
    assert str(ExpiredTokenError("expired")) == "expired"
    assert str(WrongTokenTypeError("nope")) == "nope"
    assert str(DuplicateEmailError("dup")) == "dup"
    assert str(DuplicateOAuthAccountError("link-dup")) == "link-dup"
