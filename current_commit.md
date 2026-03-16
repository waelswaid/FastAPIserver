# Security & Bug Fixes — Auth Session (2026-03-16)

## 1. Email Link Format Mismatch (Bug Fix)

**Problem:** Email templates constructed links like `{APP_BASE_URL}/verify-email?token=...` and `{APP_BASE_URL}/reset-password?token=...`, but the API only had POST endpoints at `/api/auth/verify-email` and `/api/auth/reset-password` expecting the token in the request body. Clicking the email link would 404.

**Fix:**
- **`app/utils/email.py`** — Updated both link paths to include `/api/auth/`:
  - `{APP_BASE_URL}/api/auth/reset-password?token=...`
  - `{APP_BASE_URL}/api/auth/verify-email?token=...`
- **`app/api/routes/auth_routes.py`** — Added GET endpoints to handle email click-throughs:
  - `GET /api/auth/verify-email?token=...` — completes verification directly
  - `GET /api/auth/reset-password?token=...` — validates the token and returns it so a frontend can render a "set new password" form
- Existing POST endpoints remain unchanged for programmatic API use.

**Files changed:**
- `app/utils/email.py`
- `app/api/routes/auth_routes.py`

---

## 2. Rate Limiting (Security Enhancement)

**Problem:** No rate limiting on `/forgot-password`, `/resend-verification`, or `/reset-password` — enabling email flooding and brute-force attacks.

**Fix:**
- **`app/api/dependencies/rate_limiter.py`** (new file) — In-memory sliding window rate limiter implemented as a FastAPI dependency:
  - `RateLimiter` class with configurable `max_requests`, `window_seconds`, and optional `use_email_key` for IP+email composite keys
  - Thread-safe via `threading.Lock`
  - Uses `await request.body()` (cached by Starlette) so downstream Pydantic body parsing still works
  - Returns `429 Too Many Requests` when limit is exceeded
- **`app/api/routes/auth_routes.py`** — Applied rate limiters to three routes:
  - `POST /forgot-password` — 5 requests/hour per IP+email
  - `POST /resend-verification` — 5 requests/hour per IP+email
  - `POST /reset-password` — 10 requests/hour per IP

**Files changed:**
- `app/api/dependencies/rate_limiter.py` (new)
- `app/api/routes/auth_routes.py`

---

## 3. Race Conditions in verify_email_token() and reset_password() (Bug Fix)

**Problem:** Both functions had check-then-act gaps. All guards (is_blacklisted? is_verified? jti match?) were reads, and the mutation (blacklist + update) happened later. A second concurrent request could pass all checks before the first committed, allowing double verification or double password reset.

**Fix:**
- **`app/repositories/user_repository.py`** — Added `find_user_by_id_for_update()` using `SELECT ... FOR UPDATE` to acquire a row-level lock on the user row.
- **`app/services/auth_services.py`** — Both `verify_email_token()` and `reset_password()`:
  - User lookup switched from `find_user_by_id()` to `find_user_by_id_for_update()`
  - The second concurrent request now blocks at the SELECT until the first commits, then sees the updated state and rejects
  - Blacklist insert in `reset_password()` changed to `commit=False` so it commits atomically with `update_password()`
  - Removed `IntegrityError` try/catch blocks — no longer needed since the lock prevents the race

**Files changed:**
- `app/repositories/user_repository.py`
- `app/services/auth_services.py`

---

## 4. Silent Email Send Failure (Bug Fix)

**Problem:** In `request_password_reset()` and `resend_verification_email()`, Mailgun failures were silently swallowed — the function returned as if the email was sent. Users had no way to know the email wasn't delivered.

**Fix:**
- **`app/services/auth_services.py`** — Both functions now:
  - Log the error via `logger.error()` for operator visibility
  - Raise `HTTPException(status_code=503, detail="Unable to send email. Please try again later.")` so the user knows to retry
  - 503 does not leak email existence since the error is returned regardless of whether the email was found

**Files changed:**
- `app/services/auth_services.py`

---

## 5. Wrong Expiration on Old Token Blacklist Entry (Bug Fix)

**Problem:** When a user requests a new password reset, the old token's JTI was blacklisted with `now() + 15min` instead of the old token's actual expiration. If the old token was issued 10 minutes ago (5 minutes remaining), the blacklist entry would over-extend by 10 minutes.

**Fix:**
- **`app/models/user.py`** — Added `password_reset_jti_expires_at` column (`DateTime(timezone=True)`, nullable) to store the actual expiration alongside the JTI.
- **`app/repositories/user_repository.py`** — `set_password_reset_jti()` now accepts and stores `expires_at`; `update_password()` clears both `password_reset_jti` and `password_reset_jti_expires_at`.
- **`app/services/auth_services.py`** — `request_password_reset()` decodes the new token once, extracts both JTI and exp, passes `new_expires_at` when saving; uses the stored `user.password_reset_jti_expires_at` when blacklisting the old token.
- **`migrations/versions/0b19ff09313e_add_password_reset_jti_expires_at_to_.py`** (new) — Alembic migration adding the column.

**Files changed:**
- `app/models/user.py`
- `app/repositories/user_repository.py`
- `app/services/auth_services.py`
- `migrations/versions/0b19ff09313e_add_password_reset_jti_expires_at_to_.py` (new)

---
