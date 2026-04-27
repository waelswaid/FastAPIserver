"""Global FastAPI exception handlers for domain exceptions.

Each handler maps a domain exception to a JSONResponse with a stable
status code and `{"detail": "..."}` body. Detail text is canonical here
— call sites can raise with or without a message; the handler ignores
the message and emits the canonical text. This keeps the public API
contract centralized.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import (
    DuplicateEmailError,
    DuplicateOAuthAccountError,
    ExpiredTokenError,
    InvalidTokenError,
    WrongTokenTypeError,
)


async def duplicate_email_handler(_request: Request, _exc: DuplicateEmailError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "A user with that email already exists."},
    )


async def duplicate_oauth_account_handler(_request: Request, _exc: DuplicateOAuthAccountError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "This account is already linked to another user."},
    )


async def invalid_token_handler(_request: Request, _exc: InvalidTokenError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Invalid token"})


async def expired_token_handler(_request: Request, _exc: ExpiredTokenError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Token has expired"})


async def wrong_token_type_handler(_request: Request, _exc: WrongTokenTypeError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Invalid token type"})


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the given app."""
    app.add_exception_handler(DuplicateEmailError, duplicate_email_handler)
    app.add_exception_handler(DuplicateOAuthAccountError, duplicate_oauth_account_handler)
    app.add_exception_handler(InvalidTokenError, invalid_token_handler)
    app.add_exception_handler(ExpiredTokenError, expired_token_handler)
    app.add_exception_handler(WrongTokenTypeError, wrong_token_type_handler)
