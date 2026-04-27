"""Unit tests for the domain exception hierarchy."""
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


import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.exception_handlers import register_exception_handlers


def _build_probe_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/probe-duplicate-email")
    def probe_dup_email():
        raise DuplicateEmailError("A user with that email already exists.")

    @app.get("/probe-duplicate-oauth")
    def probe_dup_oauth():
        raise DuplicateOAuthAccountError("This account is already linked to another user.")

    @app.get("/probe-invalid")
    def probe_invalid():
        raise InvalidTokenError()

    @app.get("/probe-expired")
    def probe_expired():
        raise ExpiredTokenError()

    @app.get("/probe-wrong-type")
    def probe_wrong_type():
        raise WrongTokenTypeError()

    return app


@pytest.fixture()
def probe_client():
    return TestClient(_build_probe_app())


def test_handler_duplicate_email_returns_409(probe_client):
    resp = probe_client.get("/probe-duplicate-email")
    assert resp.status_code == 409
    assert resp.json() == {"detail": "A user with that email already exists."}


def test_handler_duplicate_oauth_returns_409(probe_client):
    resp = probe_client.get("/probe-duplicate-oauth")
    assert resp.status_code == 409
    assert resp.json() == {"detail": "This account is already linked to another user."}


def test_handler_invalid_token_returns_401(probe_client):
    resp = probe_client.get("/probe-invalid")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token"}


def test_handler_expired_token_returns_401(probe_client):
    resp = probe_client.get("/probe-expired")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Token has expired"}


def test_handler_wrong_token_type_returns_401(probe_client):
    resp = probe_client.get("/probe-wrong-type")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token type"}
