# Domain Exceptions + Repository Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad-hoc `IntegrityError` / `ValueError` handling with a typed domain exception hierarchy mapped to HTTP responses by global FastAPI handlers, while preserving the public API contract (status codes + `detail` text).

**Architecture:** Define `DomainError` base in `app/exceptions.py` with `TokenError` and unique-constraint subclasses. Token decode errors in `app/utils/tokens.py` raise typed `TokenError` subclasses. Repos catch `IntegrityError` → raise domain duplicates. New `app/api/exception_handlers.py` registers handlers in `main.py` that emit `JSONResponse(status_code, {"detail": "..."})`. Services stop translating these errors except in three documented carve-outs (status-code-leak suppression in password-reset / resend-verify, deliberate best-effort swallow in `delete_own_account`, and the verify-email / reset-password flows that map token-as-credential errors to **400** rather than 401).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, PyJWT, pytest.

**Spec:** `docs/superpowers/specs/2026-04-27-domain-exceptions-design.md`

---

## File Map

**Modified:**
- `app/exceptions.py` — expand from 3 lines to full hierarchy.
- `app/main.py` — register exception handlers.
- `app/utils/tokens.py` — replace 6 `raise ValueError(...)` sites with typed exceptions.
- `app/repositories/oauth_account_repository.py` — wrap `create_oauth_account` writes in `try/except IntegrityError`.
- `app/api/dependencies/auth_dependency.py` — remove ValueError translation at line 28; keep the uuid one at line 41.
- `app/services/auth_services.py` — remove translations at lines 77, 121; type carve-outs at lines 141, 202, 236.
- `app/services/user_services.py` — remove DuplicateEmailError translation at line 21; type swallows at lines 50, 60.
- `app/services/admin_services.py` — remove DuplicateEmailError translation at line 77.

**Created:**
- `app/api/exception_handlers.py` — global handler functions + a `register_exception_handlers(app)` setup function.
- `tests/test_exceptions.py` — unit tests for exception classes, token raise sites, oauth duplicate, and handler responses.

---

### Task 1: Define exception hierarchy

**Files:**
- Modify: `app/exceptions.py`
- Test: `tests/test_exceptions.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_exceptions.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py -v`
Expected: FAIL with `ImportError: cannot import name 'DomainError' from 'app.exceptions'` (or similar).

- [ ] **Step 3: Replace `app/exceptions.py` with the full hierarchy**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_exceptions.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `pytest tests/ -v`
Expected: all existing tests PASS (the existing `DuplicateEmailError` import still works because the class name is unchanged).

- [ ] **Step 6: Commit**

```bash
git add app/exceptions.py tests/test_exceptions.py
git commit -m "refactor(exceptions): introduce DomainError + TokenError hierarchy"
```

---

### Task 2: Create global exception handlers and register them

**Files:**
- Create: `app/api/exception_handlers.py`
- Modify: `app/main.py`
- Test: `tests/test_exceptions.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_exceptions.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py -v -k handler`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.exception_handlers'`.

- [ ] **Step 3: Create `app/api/exception_handlers.py`**

```python
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
```

- [ ] **Step 4: Wire handlers into `app/main.py`**

In `app/main.py`, immediately after `app = FastAPI(lifespan=lifespan)` (currently line 40), add:

```python
from app.api.exception_handlers import register_exception_handlers
register_exception_handlers(app)
```

The `register_exception_handlers` import can be hoisted to the top imports block alongside the other `app.api.*` imports if you prefer; either placement is fine.

- [ ] **Step 5: Run handler tests to verify they pass**

Run: `pytest tests/test_exceptions.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 6: Run full test suite to confirm no regressions**

Run: `pytest tests/ -v`
Expected: all existing tests PASS. No code currently raises domain exceptions in production paths, so the handlers are dormant.

- [ ] **Step 7: Commit**

```bash
git add app/api/exception_handlers.py app/main.py tests/test_exceptions.py
git commit -m "feat(exceptions): add global handlers for DomainError subclasses"
```

---

### Task 3: Replace `ValueError` in `tokens.py` and type the carve-out catches

**Files:**
- Modify: `app/utils/tokens.py`
- Modify: `app/services/auth_services.py` (lines 141, 202, 236)
- Modify: `app/services/user_services.py` (lines 50, 60)
- Test: `tests/test_exceptions.py` (extend)

This task changes what `tokens.py` raises **and** updates the three "swallow / map-to-400" carve-out sites in the same commit so the test suite stays green throughout. The "remove unused try/except" cleanup happens in Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_exceptions.py`:

```python
from datetime import datetime, timedelta, timezone
import jwt as pyjwt

from app.core.config import settings
from app.utils.tokens import JWTConfig, JWTUtility


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_exceptions.py -v -k "raises_"`
Expected: 3 FAILS — current `tokens.py` raises `ValueError`, not the new typed exceptions.

- [ ] **Step 3: Update `app/utils/tokens.py`**

At the top of the file, change the imports:

```python
from jwt import ExpiredSignatureError
from jwt import InvalidTokenError as JWTInvalidTokenError
from app.exceptions import (
    InvalidTokenError,
    ExpiredTokenError,
    WrongTokenTypeError,
)
```

(Replace the existing `from jwt import ExpiredSignatureError, InvalidTokenError` line.)

Replace the body of `_decode_token` (currently lines 92–102) with:

```python
def _decode_token(self, token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            self.config.public_key,
            algorithms=[self.config.algorithm],
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError() from exc
    except JWTInvalidTokenError as exc:
        raise InvalidTokenError() from exc
```

Replace each of the four type-mismatch raises in `decode_access_token`, `decode_refresh_token`, `decode_password_reset_token`, `decode_email_verification_token` (currently lines 109, 117, 132, 147). For example, in `decode_access_token`:

```python
def decode_access_token(self, token: str) -> Dict[str, Any]:
    payload = self._decode_token(token)
    if payload.get("type") != "access":
        raise WrongTokenTypeError()
    return payload
```

Apply the same pattern to the other three decode methods. The `raise WrongTokenTypeError()` body is identical for all four; the message-string suffix from the old code is dropped (the global handler owns canonical text).

- [ ] **Step 4: Update the three carve-out call sites**

In `app/services/auth_services.py`:

Line 141 (`logout`, best-effort refresh-token blacklist):

```python
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti is not None and rt_exp is not None:
                rt_expires_at = datetime.fromtimestamp(rt_exp, tz=timezone.utc)
                await add_to_blacklist(rt_jti, rt_expires_at)
        except TokenError:
            pass
```

Lines 199–203 (`verify_email_token`, maps to **400** because token-as-credential, not bearer-auth):

```python
async def verify_email_token(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_email_verification_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
```

Lines 233–237 (`reset_password`, same reasoning):

```python
async def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt_gen.decode_password_reset_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
```

Add the import at the top of `app/services/auth_services.py`:

```python
from app.exceptions import TokenError
```

In `app/services/user_services.py`, lines 44–61 (`delete_own_account`, deliberate best-effort swallow):

```python
    try:
        payload = jwt_gen.decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            await add_to_blacklist(jti, datetime.fromtimestamp(exp, tz=timezone.utc))
    except TokenError:
        pass

    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti and rt_exp:
                await add_to_blacklist(rt_jti, datetime.fromtimestamp(rt_exp, tz=timezone.utc))
        except TokenError:
            pass
```

Add the import at the top of `app/services/user_services.py`:

```python
from app.exceptions import TokenError
```

(Note: `from app.exceptions import DuplicateEmailError` already exists; just add `TokenError` to the existing line, or import on a new line.)

- [ ] **Step 5: Run the new exception tests**

Run: `pytest tests/test_exceptions.py -v`
Expected: all PASS, including the new `_raises_` tests.

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all existing tests PASS. The four `except ValueError` blocks remaining in `auth_services.py` (lines 77, 121) and `auth_dependency.py` (line 28) no longer match the new TokenError types — exceptions propagate to the handler, which returns 401 with canonical text. Tests assert on status codes only, so they still pass. (Verified during plan authorship by `grep`-ing for token-error message strings in tests; no matches.)

If a test fails on a status-code mismatch (e.g. test expected 400 but got 401), it means a verify-email or reset-password carve-out was missed in Step 4 above — re-grep for `decode_X_token` usage in `app/services/` and confirm each site is in one of: removed-in-Task-4 (returns 401 via handler), kept-as-400-carve-out (`except TokenError → HTTPException(400)`), or kept-as-swallow-carve-out (`except TokenError: pass`).

- [ ] **Step 7: Commit**

```bash
git add app/utils/tokens.py app/services/auth_services.py app/services/user_services.py tests/test_exceptions.py
git commit -m "refactor(tokens): raise typed TokenError subclasses; type carve-out catches"
```

---

### Task 4: Remove dead `try/except ValueError` blocks now covered by handler

**Files:**
- Modify: `app/services/auth_services.py` (lines 75–78, 119–122)
- Modify: `app/api/dependencies/auth_dependency.py` (lines 26–29)

These blocks no longer catch anything (since `TokenError` is not a `ValueError`); the global handler now produces the same 401 response. Pure cleanup.

- [ ] **Step 1: Edit `app/services/auth_services.py`**

In `refresh_access_token`, replace lines 75–78:

```python
async def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str]:
    try:
        payload = jwt_gen.decode_refresh_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
```

with:

```python
async def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, str]:
    payload = jwt_gen.decode_refresh_token(refresh_token)
```

(The remaining `try/except ValueError` block on the `uuid.UUID(sub)` call a few lines below stays — it catches a genuine Python `ValueError` from uuid parsing.)

In `logout`, replace lines 117–122:

```python
async def logout(token: str, refresh_token: str | None = None) -> None:
    try:
        # extracts the payload from the token
        payload = jwt_gen.decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

with:

```python
async def logout(token: str, refresh_token: str | None = None) -> None:
    payload = jwt_gen.decode_access_token(token)
```

- [ ] **Step 2: Edit `app/api/dependencies/auth_dependency.py`**

Replace lines 24–29:

```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(status_code=401, detail="Invalid credentials")

    try:
        payload = jwt_gen.decode_access_token(token)
    except ValueError:
        raise credentials_error
```

with:

```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(status_code=401, detail="Invalid credentials")
    payload = jwt_gen.decode_access_token(token)
```

(Subsequent `if jti is None or await is_blacklisted(jti): raise credentials_error` checks remain.)

The remaining `except ValueError` at line 41 (uuid parsing) stays.

**Behavior change note:** previously, an invalid bearer token returned `{"detail": "Invalid credentials"}`; now it returns `{"detail": "Invalid token"}` or `{"detail": "Token has expired"}` from the global handler. Status code is 401 in both cases. No test asserts on the `detail` text for these paths (verified during plan authorship via `grep -r "Invalid credentials" tests/` against actual assertions — only the password-mismatch path uses that string).

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS.

If `test_account_deletion.py::test_delete_with_invalid_credentials` or similar fails on a `detail` assertion, check whether the test asserts on `"Invalid credentials"` for a *bearer-token-invalid* scenario (would now be `"Invalid token"`); update the test to assert on status code only, or accept either string. Most likely no change needed.

- [ ] **Step 4: Commit**

```bash
git add app/services/auth_services.py app/api/dependencies/auth_dependency.py
git commit -m "refactor(auth): remove dead ValueError catches; rely on global handler"
```

---

### Task 5: Catch `IntegrityError` in `oauth_account_repository.create_oauth_account`

**Files:**
- Modify: `app/repositories/oauth_account_repository.py`
- Test: `tests/test_exceptions.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_exceptions.py`:

```python
import uuid as _uuid

from app.repositories.oauth_account_repository import create_oauth_account


def test_create_oauth_account_duplicate_raises(db_session, create_test_user):
    user, _ = create_test_user(email="oauth-dup@example.com")
    create_oauth_account(db_session, user.id, "google", "google-sub-123")

    other_user, _ = create_test_user(email="oauth-dup-2@example.com")
    with pytest.raises(DuplicateOAuthAccountError):
        create_oauth_account(db_session, other_user.id, "google", "google-sub-123")
```

(`db_session` and `create_test_user` come from `tests/conftest.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py::test_create_oauth_account_duplicate_raises -v`
Expected: FAIL — currently raises `sqlalchemy.exc.IntegrityError`, not the domain exception.

- [ ] **Step 3: Update `app/repositories/oauth_account_repository.py`**

Replace the file with:

```python
import uuid
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import DuplicateOAuthAccountError
from app.models.oauth_account import OAuthAccount


def find_by_provider_and_provider_user_id(
    db: Session, provider: str, provider_user_id: str
) -> Optional[OAuthAccount]:
    return (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )


def create_oauth_account(
    db: Session,
    user_id: uuid.UUID,
    provider: str,
    provider_user_id: str,
    commit: bool = True,
) -> OAuthAccount:
    account = OAuthAccount(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    db.add(account)
    try:
        if commit:
            db.commit()
            db.refresh(account)
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        raise DuplicateOAuthAccountError(
            "This account is already linked to another user."
        )
    return account


def find_by_user_id(db: Session, user_id: uuid.UUID) -> Sequence[OAuthAccount]:
    return db.query(OAuthAccount).filter(OAuthAccount.user_id == user_id).all()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_exceptions.py::test_create_oauth_account_duplicate_raises -v`
Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS. The Google OAuth integration tests do not currently trigger the duplicate path (no test in `test_google_oauth.py` registers two users to the same provider sub), so behavior is unchanged for existing flows.

- [ ] **Step 6: Commit**

```bash
git add app/repositories/oauth_account_repository.py tests/test_exceptions.py
git commit -m "refactor(repo): catch IntegrityError in create_oauth_account → DuplicateOAuthAccountError"
```

---

### Task 6: Remove `DuplicateEmailError → HTTPException` translations in services

**Files:**
- Modify: `app/services/user_services.py` (lines 18–22)
- Modify: `app/services/admin_services.py` (lines 75–78)

The global handler now returns 409 + canonical message for `DuplicateEmailError`. The two service-level translations are dead code.

- [ ] **Step 1: Edit `app/services/user_services.py`**

Replace lines 18–22:

```python
def user_create(db: Session, user: UserCreate):
    try:
        new_user = user_repository.create_user(db=db, user_in=user)
    except DuplicateEmailError as e:
        raise HTTPException(status_code=409, detail=str(e))
    logger.info("audit: event=registration user_id=%s email=%s", new_user.id, new_user.email)
```

with:

```python
def user_create(db: Session, user: UserCreate):
    new_user = user_repository.create_user(db=db, user_in=user)
    logger.info("audit: event=registration user_id=%s email=%s", new_user.id, new_user.email)
```

The `DuplicateEmailError` import at line 8 is now unused. Edit the import line surgically — remove only `DuplicateEmailError`, keeping the `TokenError` import that Task 3 added (the line should read `from app.exceptions import TokenError`). Verify by running `python -c "import app.services.user_services"` — should exit cleanly with no import errors.

- [ ] **Step 2: Edit `app/services/admin_services.py`**

Replace lines 74–78 in `invite_user`:

```python
    else:
        try:
            user = create_invited_user(db, email)
        except DuplicateEmailError:
            raise HTTPException(status_code=409, detail="A user with that email already exists")
```

with:

```python
    else:
        user = create_invited_user(db, email)
```

If `DuplicateEmailError` is no longer used elsewhere in this file, remove the import at line 10.

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests PASS. `test_registration.py::test_register_duplicate_email` and `test_admin_management.py::test_invite_existing_user` (or equivalents) verify the 409 response is preserved.

- [ ] **Step 4: Commit**

```bash
git add app/services/user_services.py app/services/admin_services.py
git commit -m "refactor(services): remove DuplicateEmailError translation; rely on global handler"
```

---

### Task 7: Final verification

**Files:** none modified — verification only.

- [ ] **Step 1: Re-run the full suite with coverage**

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Expected: all tests PASS. Coverage on `app/exceptions.py` and `app/api/exception_handlers.py` should be ≥ 90% from the new tests in `test_exceptions.py`.

- [ ] **Step 2: Confirm no remaining `except ValueError:` for token decoding**

Run: `grep -n "except ValueError" app/services/ app/api/dependencies/auth_dependency.py`
Expected output: only the `uuid.UUID(sub)` ValueError catches remain (search for `uuid` near each match to confirm).

- [ ] **Step 3: Confirm `IntegrityError` is caught everywhere it can be raised**

Run: `grep -rn "db.commit\|db.flush" app/repositories/`
For each write site, confirm there is either a surrounding `try/except IntegrityError` or that the underlying table has no unique constraint that could be violated by that path. The two write paths that need it (`user_repository.create_user`, `user_repository.create_invited_user`, `oauth_account_repository.create_oauth_account`) are the only ones with unique constraints across non-PK columns.

- [ ] **Step 4: Manual smoke (optional, requires running app)**

Start the app: `uvicorn app.main:app --reload` (in a separate shell with valid `.env`).

Smoke checks:

```bash
# Duplicate email → 409
curl -s -X POST http://localhost:8000/api/users/create \
  -H "Content-Type: application/json" \
  -d '{"first_name":"a","last_name":"b","email":"dup@example.com","password":"pass12345"}'
# Then re-run the same command — second response should be:
#   {"detail":"A user with that email already exists."}  (HTTP 409)

# Garbage bearer token → 401
curl -s -i http://localhost:8000/api/users/me -H "Authorization: Bearer garbage"
# Expect HTTP/1.1 401 with {"detail":"Invalid token"}

# Refresh token in Authorization header (wrong type) → 401
# (Login first, copy refresh_token from cookie, then:)
curl -s -i http://localhost:8000/api/users/me -H "Authorization: Bearer <REFRESH_TOKEN_HERE>"
# Expect HTTP/1.1 401 with {"detail":"Invalid token type"}
```

- [ ] **Step 5: No commit needed for verification — slice complete**

If all checks pass, the slice is ready. Optional final commit:

```bash
git log --oneline master..HEAD
# Confirm 6 commits from this slice (Tasks 1–6).
```
