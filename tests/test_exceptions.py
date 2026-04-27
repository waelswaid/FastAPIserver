"""Unit tests for the domain exception hierarchy."""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.exceptions import (
    DomainError,
    DuplicateEmailError,
    DuplicateOAuthAccountError,
    TokenError,
    InvalidTokenError,
    ExpiredTokenError,
    WrongTokenTypeError,
)
from app.api.exception_handlers import register_exception_handlers
from app.utils.tokens import JWTConfig, JWTUtility


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


def _build_probe_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/probe-duplicate-email")
    def probe_dup_email():
        raise DuplicateEmailError()

    @app.get("/probe-duplicate-oauth")
    def probe_dup_oauth():
        raise DuplicateOAuthAccountError()

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


def _make_jwt_utility() -> JWTUtility:
    return JWTUtility(
        JWTConfig(
            private_key=settings.JWT_PRIVATE_KEY,
            public_key=settings.JWT_PUBLIC_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
    )


def test_decode_garbage_token_raises_invalid_token_error():
    util = _make_jwt_utility()
    with pytest.raises(InvalidTokenError):
        util.decode_access_token("not-a-jwt")


def test_decode_expired_token_raises_expired_token_error():
    util = _make_jwt_utility()
    expired = pyjwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "jti": "x",
        },
        settings.JWT_PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(ExpiredTokenError):
        util.decode_access_token(expired)


def test_decode_wrong_type_raises_wrong_token_type_error():
    util = _make_jwt_utility()
    refresh_token = util.create_refresh_token("00000000-0000-0000-0000-000000000000")
    with pytest.raises(WrongTokenTypeError):
        util.decode_access_token(refresh_token)
