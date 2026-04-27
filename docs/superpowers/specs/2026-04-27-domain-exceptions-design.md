# Slice 1 — Domain Exceptions + Repository Hardening

**Date:** 2026-04-27
**Status:** Approved (pending plan)
**Scope:** First slice of an 8-slice piecemeal refactor of `auth-system`.

## Goal

Replace generic `IntegrityError` and `ValueError` raises with a small, typed domain exception hierarchy. Map exceptions to HTTP responses in **one** place via FastAPI exception handlers, so services stop translating errors by hand.

This slice is structural cleanup. The public HTTP API contract (status codes, response body shape, message text) does not change.

## Motivation

The current codebase mixes three error-handling styles:

1. **Repo writes mostly catch `IntegrityError`** — but `oauth_account_repository.create_oauth_account` does not, so a duplicate `(provider, provider_user_id)` would surface as a SQLAlchemy error to the caller.
2. **`tokens.py` raises raw `ValueError`** at six sites (`_decode_token` raises 2 different conditions; each of four typed decode methods raises one type-mismatch).
3. **Services translate by hand** — 12 `except ValueError → HTTPException(401)` blocks scattered across `auth_services.py`, `user_services.py`, and `auth_dependency.py`. Two more sites translate `DuplicateEmailError → HTTPException(409)`. Two of the 12 (in `delete_own_account`) are deliberate swallows, not translations.

This means HTTP status codes and message strings live in many places. A new auth flow has to remember to translate by hand. Project rule (CLAUDE.md): *"Catch IntegrityError at the repository layer and raise domain-specific exceptions"* — currently honored only for users, not OAuth accounts.

## Scope (in)

- Expand `app/exceptions.py` with a typed hierarchy.
- Repository: catch `IntegrityError` at every write site that has a unique constraint; raise the matching domain exception.
- `app/utils/tokens.py`: replace four `raise ValueError(...)` with typed exceptions.
- New `app/api/exception_handlers.py`; registered from `main.py`.
- Service-layer cleanup: remove the 12 `try/except ValueError → HTTPException` and 2 `try/except DuplicateEmailError → HTTPException` blocks where the global handler now covers them.
- `app/api/dependencies/auth_dependency.py`: drop the two manual `ValueError` translations (lines 28, 41).
- Tests: keep existing passing (message strings preserved); add unit tests for the new exception types and repo coverage.

## Scope (out)

- Status-code-leak carve-outs: `request_password_reset`, `resend_verification_email`, and any flow that intentionally returns a non-error response when an account is missing. These keep explicit `except DomainError: return` blocks — by design, not regression.
- Adding a `code` field to error bodies. Body shape stays `{"detail": "..."}`.
- Anything in slices 2–8: `auth_services.py` split, ephemeral state on `users`, fail-closed Redis, async correctness, config/enums, layering audit, test/CI hygiene.
- The `pending_actions.upsert_action` race condition (slice 4 territory).
- The `token_blacklist_repository` fail-open behavior (slice 4 territory).

## Design

### Exception hierarchy (`app/exceptions.py`)

```
DomainError(Exception)             # base — never raised directly
├── DuplicateEmailError            # existing, kept as-is
├── DuplicateOAuthAccountError     # new — provider + provider_user_id collision
└── TokenError
    ├── InvalidTokenError          # signature/format/missing claim
    ├── ExpiredTokenError          # signature valid, exp passed
    └── WrongTokenTypeError        # decoded but `type` claim mismatched
```

Flat module, no subpackage. ~25 lines total.

### Status-code mapping (`app/api/exception_handlers.py`)

Single new file. Each handler returns `JSONResponse(status_code=X, content={"detail": "..."})` so the response body shape and message text match what services currently raise via `HTTPException(detail=...)`.

| Exception | HTTP | `detail` |
|---|---|---|
| `DuplicateEmailError` | 409 | `"A user with that email already exists."` |
| `DuplicateOAuthAccountError` | 409 | `"This account is already linked to another user."` |
| `InvalidTokenError` | 401 | `"Invalid token"` |
| `ExpiredTokenError` | 401 | `"Token has expired"` |
| `WrongTokenTypeError` | 401 | `"Invalid token type"` |

`main.py` calls `register_exception_handlers(app)` (or equivalent) once during app construction. No middleware ordering concerns — FastAPI handlers run after middleware.

### Repository changes

**`oauth_account_repository.create_oauth_account`** — wrap commit/flush in `try/except IntegrityError`, rollback, raise `DuplicateOAuthAccountError`. Mirrors `user_repository.create_user`.

**`user_repository.create_user`, `create_invited_user`** — already correct, no change.

### Token changes (`app/utils/tokens.py`)

Six raise sites collapse to three exception types:

1. `_decode_token` line 100 (`ExpiredSignatureError`) → `raise ExpiredTokenError(...) from exc`
2. `_decode_token` line 102 (PyJWT's `InvalidTokenError`) → `raise InvalidTokenError(...) from exc`
3. `decode_access_token` type check (line 109) → `WrongTokenTypeError`
4. `decode_refresh_token` type check (line 117) → `WrongTokenTypeError`
5. `decode_password_reset_token` type check (line 132) → `WrongTokenTypeError`
6. `decode_email_verification_token` type check (line 147) → `WrongTokenTypeError`

Raise-site arguments may be empty/short — the global handler owns the canonical `detail` text for the response. No test currently asserts on the existing strings, so this is safe.

**Naming clash:** PyJWT's `InvalidTokenError` shadows our domain one. Resolve at import: `from jwt import InvalidTokenError as JWTInvalidTokenError`.

### Service changes

The pattern to remove (12 occurrences):

```python
try:
    payload = jwt_gen.decode_X_token(token)
except ValueError:
    raise HTTPException(status_code=401, detail="...")
```

becomes:

```python
payload = jwt_gen.decode_X_token(token)
```

Files and confirmed sites:

- `app/services/auth_services.py:77, 87, 121, 141, 202, 215, 236, 249` (8 sites)
- `app/services/user_services.py:50, 60` (2 sites — **deliberate swallows, not translations**. After password verification + locked-row lookup succeed, blacklisting the now-defunct tokens is best-effort. Convert to `except TokenError: pass` so the swallow remains explicit and typed.)
- `app/api/dependencies/auth_dependency.py:28, 41` (2 sites — remove)

Plus the two `DuplicateEmailError` translation sites:

- `app/services/admin_services.py:77` (in `invite_user`)
- `app/services/user_services.py:21` (in user create)

These two get removed; the global handler returns the same 409 + message.

**Carve-outs (do NOT remove):** any service flow that intentionally swallows the exception. Confirmed candidates:

- `delete_own_account` — best-effort token blacklisting after a verified delete (covered above).
- `request_password_reset` — returns silently on missing user; if the new code path can raise `DomainError`, keep an explicit catch.
- `resend_verification_email` — same shape as `request_password_reset`.

When in doubt during implementation, keep the explicit catch and document why with a one-line comment.

### Auth dependency

`app/api/dependencies/auth_dependency.py` currently catches `ValueError` twice (lines 28, 41) and raises `HTTPException(401)`. Replace with bare propagation; global handler maps to 401 + same `detail` text.

### Test plan

**Existing tests:** must continue to pass without modification, since `detail` strings and status codes are preserved. Verification step in the plan: full `pytest tests/ -v` before and after.

**Tests to add:**

1. `tests/test_exceptions.py` (new, small) — direct unit tests:
   - `_decode_token` on tampered JWT → raises `InvalidTokenError`.
   - `_decode_token` on expired JWT → raises `ExpiredTokenError`.
   - `decode_access_token(refresh_jwt)` → raises `WrongTokenTypeError`.
   - `create_oauth_account` called twice with same `(provider, provider_user_id)` → raises `DuplicateOAuthAccountError`.
2. Spot-check existing OAuth tests in `test_google_oauth.py` for any `with pytest.raises(ValueError):` or `with pytest.raises(IntegrityError):` — replace with the new typed exception.

**Tests to remove:** none expected.

## Risk

- **Public API contract:** unchanged. Status codes + `detail` text preserved per the table above. Existing test assertions verify this.
- **Migration:** none.
- **Rollback:** revert the PR; no schema or data changes.
- **Blast radius:** every auth-touching endpoint flows through the changed code, but the test suite covers each. Risk is mitigated by preserving observable behavior.

## Verification

- `pytest tests/ -v` — full suite green.
- Manual smoke: `POST /users/create` with duplicate email → 409 with same body.
- Manual smoke: `GET /users/me` with expired token → 401 with `"Token has expired"`.
- Manual smoke: `GET /users/me` with refresh token in Authorization header → 401 with `"Invalid token type"`.

## Out-of-scope follow-ups (already tracked as future slices)

- **Slice 2:** Split `auth_services.py` (356 lines).
- **Slice 4:** Fix Redis fail-open posture and `upsert_action` race.
- **Slice 7:** Remove remaining `HTTPException` raises from services as part of the broader layering audit.
