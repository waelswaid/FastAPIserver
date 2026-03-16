# Architecture — FastAPI Auth System

## Overview

A backend authentication API built with FastAPI, SQLAlchemy, and PostgreSQL. Provides user registration, email verification, JWT-based login/logout, token refresh, and password reset — all with rate limiting, token revocation, and race condition protection.

**Runtime:** Python 3.14, FastAPI 0.135, SQLAlchemy 2.0, PostgreSQL 18
**Branch:** `auth` (main branch: `main`)

---

## Project Structure

```
FastAPIapp/
    app/
        main.py                             # FastAPI app, lifespan hook, router mounting
        exceptions.py                       # DuplicateEmailError
        core/
            config.py                       # pydantic-settings: loads .env into Settings singleton
        database/
            session.py                      # SQLAlchemy engine, SessionLocal factory, get_db dependency
        models/
            base.py                         # DeclarativeBase for all ORM models
            user.py                         # User model (users table)
            token_blacklist.py              # TokenBlacklist model (token_blacklist table)
        schemas/
            users_schema.py                 # UserBase, UserCreate (input), UserRead (response)
            login_request.py                # LoginBase, LoginRequest
            token_response.py               # TokenResponse (access_token + token_type)
            password_reset_schema.py        # ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest
        repositories/
            user_repository.py              # All User DB operations (CRUD, find, update, lock)
            token_blacklist_repository.py   # Blacklist add, check, cleanup
        services/
            user_services.py                # user_create (registration + verification email)
            auth_services.py                # Login, logout, refresh, password reset, email verification
        api/
            dependencies/
                auth_dependency.py          # get_current_user (JWT validation + blacklist + password_changed_at)
                rate_limiter.py             # RateLimiter class, 3 pre-configured singleton instances
            routes/
                user_routes.py              # POST /users/create, GET /users/me
                auth_routes.py              # All auth endpoints (login, logout, refresh, reset, verify)
        utils/
            email.py                        # send_password_reset_email, send_verification_email (Mailgun)
            tokens.py                       # JWTConfig dataclass, JWTUtility class (create/decode tokens)
            security/
                password_hash.py            # hash_password, verify_password (pwdlib, Argon2/bcrypt)
    migrations/
        versions/
            d7a8851380f6_initial_schema.py
            cf997718a679_add_index_on_password_reset_jti_column.py
            ce824630f5cd_add_opaque_email_verification_and_.py
            0b19ff09313e_add_password_reset_jti_expires_at_to_.py
    tests/
        conftest.py                         # All shared fixtures (engine, db_session, client, mocks)
        test_registration.py                # 11 tests — POST /api/users/create
        test_login.py                       # 6 tests  — POST /api/auth/login
        test_token_refresh.py               # 6 tests  — POST /api/auth/refresh
        test_logout.py                      # 4 tests  — POST /api/auth/logout
        test_me.py                          # 5 tests  — GET /api/users/me
        test_forgot_password.py             # 5 tests  — POST /api/auth/forgot-password
        test_reset_password.py              # 13 tests — GET & POST /api/auth/reset-password
        test_email_verification.py          # 9 tests  — GET & POST /api/auth/verify-email
        test_resend_verification.py         # 4 tests  — POST /api/auth/resend-verification
        test_rate_limiting.py               # 4 tests  — Rate limiter behavior
    reports/
        TEST_REPORT.md                      # Full test report with conclusion
        test_report.html                    # Interactive pytest-html report
        coverage_html/                      # Line-by-line coverage browser
    alembic.ini                             # Alembic configuration
    requirements.txt                        # Pinned dependencies
    current_commit.md                       # Changelog of recent security fixes
    .env                                    # Environment variables (not committed)
```

---

## Layered Architecture

The application follows a strict layered architecture. Each layer only calls the one directly below it:

```
HTTP Layer          Routes (auth_routes.py, user_routes.py)
                        |
                    Dependencies (auth_dependency.py, rate_limiter.py)
                        |
Service Layer       Services (auth_services.py, user_services.py)
                        |
Data Layer          Repositories (user_repository.py, token_blacklist_repository.py)
                        |
ORM Layer           Models (user.py, token_blacklist.py)
                        |
                    PostgreSQL
```

**Routes** handle HTTP concerns: request parsing, response formatting, cookies, status codes.
**Services** contain business logic: validation sequences, token generation, email dispatch, error decisions.
**Repositories** are pure data access: queries, inserts, updates, row-level locks. Each function takes a `db: Session` and operates on one model.
**Models** define the database schema via SQLAlchemy ORM mapped columns.

---

## Database Schema

### `users` table

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, server_default=gen_random_uuid() | User identifier |
| name | String | NOT NULL, indexed | Display name |
| email | String | UNIQUE, NOT NULL, indexed | Login identifier |
| password_hash | String | NOT NULL | Argon2/bcrypt hash via pwdlib |
| is_verified | Boolean | NOT NULL, default=false | Email verification gate for login |
| created_at | DateTime(tz) | NOT NULL, default=now() | Account creation timestamp |
| password_changed_at | DateTime(tz) | nullable | Set on every password change; invalidates pre-change tokens |
| password_reset_jti | String | nullable, indexed | JTI of the most recent password reset token |
| password_reset_jti_expires_at | DateTime(tz) | nullable | Expiration of the above JTI (for accurate blacklisting) |
| password_reset_code | String | nullable | Opaque UUID code sent in password reset email links |
| password_reset_code_expires_at | DateTime(tz) | nullable | Expiration of the above code |
| email_verification_code | String | nullable | Opaque UUID code sent in verification email links |
| email_verification_code_expires_at | DateTime(tz) | nullable | Expiration of the above code |

### `token_blacklist` table

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| jti | String | PK | JWT ID claim of the revoked token |
| expires_at | DateTime(tz) | NOT NULL | Mirrors the token's `exp`; allows cleanup of expired entries |

---

## API Endpoints

### User Routes (prefix: `/api`)

| Method | Path | Auth | Response | Description |
|--------|------|------|----------|-------------|
| POST | /users/create | No | UserRead (200) | Register a new user; sends verification email |
| GET | /users/me | Bearer | UserRead (200) | Return current authenticated user |

### Auth Routes (prefix: `/api/auth`)

| Method | Path | Auth | Rate Limit | Response | Description |
|--------|------|------|------------|----------|-------------|
| POST | /login | No | No | TokenResponse (200) + refresh_token cookie | Authenticate; returns access + refresh tokens |
| POST | /refresh | Cookie | No | TokenResponse (200) | Exchange refresh token for new access token |
| POST | /logout | Bearer | No | 204 | Blacklist access + refresh tokens, delete cookie |
| POST | /forgot-password | No | 5/hr per IP+email | 200 | Send password reset email (if user exists + verified) |
| GET | /reset-password | No | No | 200 | Validate a reset code from email link |
| POST | /reset-password | No | 10/hr per IP | 200 | Reset password via code or JWT token |
| POST | /resend-verification | No | 5/hr per IP+email | 200 | Resend verification email (if user exists + unverified) |
| GET | /verify-email | No | No | 200 | Verify email via code from email link |
| POST | /verify-email | No | No | 200 | Verify email via JWT token |

### Request/Response Schemas

**UserCreate** (registration input):
- `name: str` (required)
- `email: EmailStr` (required)
- `password: str` (min 8, max 128)

**UserRead** (registration/me response):
- `id: UUID`, `name: str`, `email: EmailStr`, `created_at: datetime`

**LoginRequest**: `email: EmailStr`, `password: str` (min 8, max 128)

**TokenResponse**: `access_token: str`, `token_type: str` ("bearer")

**ForgotPasswordRequest**: `email: EmailStr`

**ResetPasswordRequest**: `token: str | None`, `code: str | None`, `new_password: str` (min 8, max 128)
- Validator: at least one of `token` or `code` must be provided

**VerifyEmailRequest**: `token: str`

---

## Authentication System

### Token Types

All tokens are JWTs signed with HS256 using `JWT_SECRET_KEY`. Each token contains:
- `sub` — user UUID (string)
- `type` — one of: `access`, `refresh`, `password_reset`, `email_verification`
- `iat` — issued-at timestamp
- `exp` — expiration timestamp
- `jti` — unique UUID v4 for revocation tracking

| Token Type | Expiry | Storage | Purpose |
|------------|--------|---------|---------|
| access | 30 min | Response body | Authenticate API requests via Bearer header |
| refresh | 1 day | httponly cookie (samesite=strict) | Obtain new access tokens without re-login |
| password_reset | 15 min | Server-side only (JTI stored on user) | Authorize password change |
| email_verification | 24 hours | Server-side only | Authorize email verification |

### Token Lifecycle

**Login:** Creates access + refresh tokens. Refresh token set as httponly cookie.

**Refresh:** Validates refresh token (signature, expiry, type, not blacklisted, issued after last password change). Returns new access token.

**Logout:** Blacklists both access and refresh token JTIs. Deletes refresh cookie.

**Password reset / Email verification:** Uses dual-path approach:
1. **Code path** (GET endpoints) — Opaque UUID code sent in email link. User clicks link, code is validated. For password reset, a frontend would then POST the code + new password.
2. **Token path** (POST endpoints) — JWT token for programmatic API use. JTI stored on user row for single-use enforcement.

### Token Revocation

Revocation is checked at two levels:
1. **Blacklist table** — the token's JTI is looked up in `token_blacklist`. Used for logout, superseded reset tokens, and used verification tokens.
2. **`password_changed_at` comparison** — the token's `iat` is compared to the user's `password_changed_at`. Any token issued before the last password change is rejected. This invalidates all sessions on password change without needing to enumerate and blacklist each one.

### Protected Route Flow (`get_current_user` dependency)

```
Bearer token from Authorization header
    → decode_access_token (signature, expiry, type check)
    → check JTI not blacklisted
    → find user by sub (UUID)
    → check iat >= password_changed_at
    → return User
Any failure → 401 Invalid credentials
```

---

## Rate Limiting

In-memory sliding window rate limiter implemented as a FastAPI dependency (`RateLimiter` class).

**Design:**
- Per-key hit tracking using `dict[str, list[float]]` with monotonic timestamps
- Thread-safe via `threading.Lock`
- Key is either IP-only or IP+email composite (extracted from JSON request body)
- Stale hits pruned on each check (hits older than `window_seconds` removed)
- Returns 429 when limit exceeded

**Configured limiters (singletons):**

| Limiter | Max Requests | Window | Key Type | Applied To |
|---------|-------------|--------|----------|------------|
| `forgot_password_limiter` | 5 | 1 hour | IP + email | POST /forgot-password |
| `resend_verification_limiter` | 5 | 1 hour | IP + email | POST /resend-verification |
| `reset_password_limiter` | 10 | 1 hour | IP only | POST /reset-password |

**Limitation:** In-memory storage means rate limits reset on server restart and are not shared across multiple worker processes.

---

## Email Integration

Uses the Mailgun REST API (`https://api.mailgun.net/v3/{domain}/messages`) via the `requests` library.

Two email functions in `app/utils/email.py`:
- `send_password_reset_email(to_email, code)` — sends a link to `{APP_BASE_URL}/api/auth/reset-password?code={code}`
- `send_verification_email(to_email, code)` — sends a link to `{APP_BASE_URL}/api/auth/verify-email?code={code}`

Both call `response.raise_for_status()` — failures propagate as `requests.RequestException`.

**Error handling in services:**
- Registration (`user_services.py`): Mailgun failure → 500, user is created but email not sent
- Forgot password (`auth_services.py`): Mailgun failure → 503, no state changes committed (email sent before DB writes)
- Resend verification (`auth_services.py`): Mailgun failure → 503

---

## Password Hashing

Uses `pwdlib` (adaptive hashing library) with `PasswordHash.recommended()`, which selects Argon2id as the default algorithm. Provides:
- `hash_password(password: str) -> str`
- `verify_password(password: str, hashed_password: str) -> bool`

---

## Race Condition Protection

Two operations are vulnerable to time-of-check-to-time-of-use races:

1. **Email verification** — Two concurrent requests with the same verification token could both pass the "not yet verified" check before either commits.
2. **Password reset** — Two concurrent requests with the same reset token could both pass the "JTI matches" check.

**Solution:** Both `verify_email_token()` and `reset_password()` use `SELECT ... FOR UPDATE` via `find_user_by_id_for_update()` to acquire a row-level lock on the user. The second concurrent request blocks at the SELECT until the first commits, then sees the updated state and rejects.

The same pattern is used for code-based operations via `find_user_by_verification_code_for_update()` and `find_user_by_reset_code_for_update()`.

---

## Configuration

All configuration loaded from `.env` via `pydantic-settings` at import time (`settings = Settings()` in `config.py`).

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| DATABASE_URL | Yes | — | PostgreSQL connection string |
| JWT_SECRET_KEY | Yes | — | HMAC signing secret for all JWTs |
| JWT_ALGORITHM | No | HS256 | JWT signing algorithm |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | 30 | Access token lifetime |
| ENVIRONMENT | No | development | "production" enables secure cookie flag |
| MAILGUN_API_KEY | Yes | — | Mailgun API authentication |
| MAILGUN_DOMAIN | Yes | — | Mailgun sending domain |
| MAILGUN_FROM_EMAIL | Yes | — | From address for transactional emails |
| APP_BASE_URL | No | http://localhost:8000 | Base URL for email links |
| PASSWORD_RESET_EXPIRE_MINUTES | No | 15 | Reset token/code lifetime |
| EMAIL_VERIFICATION_EXPIRE_MINUTES | No | 1440 | Verification token/code lifetime (24h) |

---

## Application Startup

The FastAPI lifespan hook (`app/main.py`) runs on startup:
1. Creates a database session
2. Calls `cleanup_expired_tokens()` — deletes blacklist entries where `expires_at < now()`
3. Closes the session

No background scheduler exists — blacklist cleanup only happens on startup.

---

## Database Migrations

Managed by Alembic. Migration files in `migrations/versions/`:

| Migration | Description |
|-----------|-------------|
| `d7a8851380f6` | Initial schema: `users` and `token_blacklist` tables |
| `cf997718a679` | Add index on `password_reset_jti` column |
| `ce824630f5cd` | Add opaque email verification and password reset code columns |
| `0b19ff09313e` | Add `password_reset_jti_expires_at` column |

Run migrations: `alembic upgrade head`
Generate new migration: `alembic revision --autogenerate -m "description"`

---

## Test Suite

67 integration tests across 10 files. **94% code coverage.**

**Infrastructure:**
- Real PostgreSQL database (`fastapiapp_test`) — no DB mocks
- Savepoint-per-test isolation: each test runs in a transaction that is rolled back, leaving no data behind
- Mailgun calls mocked via `unittest.mock.patch` on `app.utils.email.requests.post` (autouse)
- Rate limiter `_hits` dicts cleared before each test (autouse)
- `get_db` dependency overridden to yield the test session

**Run:** `pytest tests/ -v`
**Coverage:** `pytest tests/ --cov=app --cov-report=term-missing`
**Full reports:** `reports/TEST_REPORT.md`, `reports/test_report.html`, `reports/coverage_html/`

---

## Dependencies

Key packages (from `requirements.txt`):

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.135.1 | Web framework |
| uvicorn | 0.41.0 | ASGI server |
| sqlalchemy | 2.0.48 | ORM |
| psycopg2-binary | 2.9.11 | PostgreSQL driver |
| alembic | 1.18.4 | Database migrations |
| pydantic | 2.12.5 | Data validation |
| pydantic-settings | 2.13.1 | .env configuration |
| pyjwt | 2.12.1 | JWT creation/verification |
| pwdlib | 0.3.0 | Password hashing (Argon2/bcrypt) |
| email-validator | 2.3.0 | Email format validation |
| requests | 2.32.5 | HTTP client (Mailgun API) |
| pytest | 9.0.2 | Test runner |
| httpx | 0.28.1 | Required by FastAPI TestClient |
| pytest-cov | 7.0.0 | Coverage reporting |
| pytest-html | 4.2.0 | HTML test reports |

---

## Known Issues

1. **User repository raises HTTPException directly.** `create_user()` in `user_repository.py` raises `DuplicateEmailError`, but this is an HTTP concern leaking into the data layer. The service layer catches it and re-raises as `HTTPException(409)`, which is correct — but the repository should ideally raise a domain exception only.

2. **LoginRequest inherits LoginBase with no added fields.** `LoginRequest(LoginBase): pass` adds no value over using `LoginBase` directly.

3. **Email links vs POST endpoints.** Email links use GET query params (`?code=...`), but the POST endpoints expect JSON body. The GET endpoints were added to handle direct email click-throughs, but a proper password reset flow needs a frontend to intercept the GET, render a form, and POST the new password.

4. **No background blacklist cleanup.** Expired token blacklist entries are only cleaned up on application startup. A long-running server will accumulate stale rows. A periodic background task or database-level TTL would solve this.

5. **In-memory rate limiting is not distributed.** Rate limit counters live in process memory. They reset on server restart and are not shared across multiple uvicorn workers. A production deployment should use Redis or a similar shared store.

6. **No refresh token rotation.** The refresh endpoint issues a new access token but does not rotate the refresh token itself. A stolen refresh token remains valid for its full 1-day lifetime. Rotation (issue new refresh token on each use, blacklist the old one) would limit the window of compromise.
