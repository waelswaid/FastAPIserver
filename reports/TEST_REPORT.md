# Test Report — FastAPI Auth System

**Date:** 2026-03-16
**Branch:** auth
**Python:** 3.14.2
**Runner:** pytest 9.0.2
**Database:** PostgreSQL (fastapiapp_test)

---

## Summary

| Metric             | Value       |
|--------------------|-------------|
| Total tests        | 67          |
| Passed             | 67          |
| Failed             | 0           |
| Errors             | 0           |
| Skipped            | 0           |
| Duration           | ~8.6s       |
| **Code coverage**  | **94%**     |

---

## Results by Module

| Test File                      | Tests | Passed | Failed | Endpoint(s) Covered                         |
|--------------------------------|-------|--------|--------|---------------------------------------------|
| test_registration.py           | 11    | 11     | 0      | POST /api/users/create                      |
| test_login.py                  | 6     | 6      | 0      | POST /api/auth/login                        |
| test_token_refresh.py          | 6     | 6      | 0      | POST /api/auth/refresh                      |
| test_logout.py                 | 4     | 4      | 0      | POST /api/auth/logout                       |
| test_me.py                     | 5     | 5      | 0      | GET /api/users/me                           |
| test_forgot_password.py        | 5     | 5      | 0      | POST /api/auth/forgot-password              |
| test_reset_password.py         | 13    | 13     | 0      | GET & POST /api/auth/reset-password         |
| test_email_verification.py     | 9     | 9      | 0      | GET & POST /api/auth/verify-email           |
| test_resend_verification.py    | 4     | 4      | 0      | POST /api/auth/resend-verification          |
| test_rate_limiting.py          | 4     | 4      | 0      | Rate limiter behavior across 3 endpoints    |

---

## Coverage by Source File

| Source File                              | Stmts | Miss | Cover | Notes                                        |
|------------------------------------------|-------|------|-------|----------------------------------------------|
| api/routes/auth_routes.py                | 52    | 0    | 100%  |                                              |
| api/routes/user_routes.py                | 14    | 0    | 100%  |                                              |
| repositories/user_repository.py          | 60    | 0    | 100%  |                                              |
| repositories/token_blacklist_repository.py | 12  | 0    | 100%  |                                              |
| services/user_services.py                | 17    | 0    | 100%  |                                              |
| services/auth_services.py                | 178   | 17   | 90%   | Uncovered: malformed JWT sub/jti edge cases  |
| api/dependencies/auth_dependency.py      | 36    | 4    | 89%   | Uncovered: missing sub, invalid UUID in sub  |
| api/dependencies/rate_limiter.py         | 36    | 2    | 94%   | Uncovered: JSON decode error fallback        |
| utils/tokens.py                          | 59    | 5    | 92%   | Uncovered: additional_claims on some creators|
| utils/email.py                           | 10    | 0    | 100%  |                                              |
| utils/security/password_hash.py          | 6     | 0    | 100%  |                                              |
| database/session.py                      | 13    | 7    | 46%   | Expected: get_db overridden by test fixtures |
| models/*.py                              | 33    | 0    | 100%  |                                              |
| schemas/*.py                             | 28    | 0    | 100%  |                                              |
| core/config.py                           | 10    | 0    | 100%  |                                              |
| main.py                                  | 16    | 0    | 100%  |                                              |
| **TOTAL**                                | **583** | **35** | **94%** |                                          |

---

## Test Case Details

### test_registration.py — POST /api/users/create (11 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_register_success — valid registration returns 200 with UserRead fields, email sent | PASS |
| 2 | test_register_duplicate_email — already-used email returns 409 | PASS |
| 3 | test_register_email_send_failure — Mailgun failure returns 500 | PASS |
| 4 | test_register_missing_name — 422 | PASS |
| 5 | test_register_missing_email — 422 | PASS |
| 6 | test_register_missing_password — 422 | PASS |
| 7 | test_register_short_password — password < 8 chars returns 422 | PASS |
| 8 | test_register_password_too_long — password > 128 chars returns 422 | PASS |
| 9 | test_register_invalid_email_format — malformed email returns 422 | PASS |
| 10 | test_register_response_no_password_hash — response does not leak password_hash | PASS |
| 11 | test_register_user_cannot_login_before_verification — unverified user gets 403 | PASS |

### test_login.py — POST /api/auth/login (6 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_login_success — 200, access_token in body, refresh_token cookie set | PASS |
| 2 | test_login_unverified_user — 403 | PASS |
| 3 | test_login_wrong_password — 401 | PASS |
| 4 | test_login_nonexistent_email — 401 | PASS |
| 5 | test_login_short_password_rejected — 422 | PASS |
| 6 | test_login_cookie_security_flags — httponly and samesite=strict set | PASS |

### test_token_refresh.py — POST /api/auth/refresh (6 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_refresh_success — 200, new access_token returned | PASS |
| 2 | test_refresh_no_cookie — 401 | PASS |
| 3 | test_refresh_invalid_token — garbage cookie returns 401 | PASS |
| 4 | test_refresh_blacklisted_token — blacklisted JTI returns 401 | PASS |
| 5 | test_refresh_after_password_change — token before password change returns 401 | PASS |
| 6 | test_refresh_new_token_works_on_me — refreshed token is usable on /users/me | PASS |

### test_logout.py — POST /api/auth/logout (4 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_logout_success — 204, old access token rejected on /users/me | PASS |
| 2 | test_logout_no_refresh_cookie — still 204 | PASS |
| 3 | test_logout_invalid_access_token — 401 | PASS |
| 4 | test_logout_refresh_token_also_blacklisted — refresh fails after logout | PASS |

### test_me.py — GET /api/users/me (5 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_get_me_success — 200, correct user data | PASS |
| 2 | test_get_me_no_token — 401 | PASS |
| 3 | test_get_me_invalid_token — 401 | PASS |
| 4 | test_get_me_blacklisted_token — 401 | PASS |
| 5 | test_get_me_token_before_password_change — 401 | PASS |

### test_forgot_password.py — POST /api/auth/forgot-password (5 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_forgot_password_existing_email — 200, email sent | PASS |
| 2 | test_forgot_password_nonexistent_email — 200, no email sent | PASS |
| 3 | test_forgot_password_unverified_user — 200, no email sent | PASS |
| 4 | test_forgot_password_email_failure — Mailgun failure returns 503 | PASS |
| 5 | test_forgot_password_second_request_invalidates_first_token — first code/token invalidated | PASS |

### test_reset_password.py — GET & POST /api/auth/reset-password (13 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_validate_reset_code_success — GET with valid code returns 200 | PASS |
| 2 | test_validate_reset_code_invalid — GET with bogus code returns 400 | PASS |
| 3 | test_validate_reset_code_expired — GET with expired code returns 400 | PASS |
| 4 | test_reset_password_via_code_success — POST with code resets password, login works | PASS |
| 5 | test_reset_password_via_code_reused — same code twice returns 400 | PASS |
| 6 | test_reset_password_via_token_success — POST with valid JWT returns 200 | PASS |
| 7 | test_reset_password_via_token_expired — expired JWT returns 400 | PASS |
| 8 | test_reset_password_via_token_blacklisted — blacklisted JTI returns 400 | PASS |
| 9 | test_reset_password_missing_token_and_code — neither provided returns 422 | PASS |
| 10 | test_reset_password_short_new_password — new password < 8 chars returns 422 | PASS |
| 11 | test_reset_password_via_code_expired_post — POST with expired code returns 400 | PASS |
| 12 | test_reset_password_via_token_jti_mismatch — token JTI != stored JTI returns 400 | PASS |
| 13 | test_reset_password_via_token_then_login — new password works, old rejected | PASS |

### test_email_verification.py — GET & POST /api/auth/verify-email (9 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_verify_via_code_success — valid code sets is_verified=True | PASS |
| 2 | test_verify_via_code_invalid — bogus code returns 400 | PASS |
| 3 | test_verify_via_code_expired — expired code returns 400 | PASS |
| 4 | test_verify_via_code_already_verified — already verified returns 400 | PASS |
| 5 | test_verify_via_token_success — valid JWT sets is_verified=True | PASS |
| 6 | test_verify_via_token_expired — expired JWT returns 400 | PASS |
| 7 | test_verify_via_token_already_verified — already verified returns 400 | PASS |
| 8 | test_verify_via_token_blacklisted_jti — blacklisted JTI returns 400 | PASS |
| 9 | test_verify_then_login_works — end-to-end: register -> verify -> login | PASS |

### test_resend_verification.py — POST /api/auth/resend-verification (4 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_resend_success — unverified user gets 200, email sent | PASS |
| 2 | test_resend_already_verified — 200, no email sent | PASS |
| 3 | test_resend_nonexistent_email — 200, no email sent | PASS |
| 4 | test_resend_email_failure — Mailgun failure returns 503 | PASS |

### test_rate_limiting.py (4 tests)

| # | Test | Status |
|---|------|--------|
| 1 | test_forgot_password_rate_limit — 6th request returns 429 (limit: 5/hr) | PASS |
| 2 | test_resend_verification_rate_limit — 6th request returns 429 (limit: 5/hr) | PASS |
| 3 | test_reset_password_rate_limit — 11th request returns 429 (limit: 10/hr) | PASS |
| 4 | test_rate_limit_different_emails_independent — separate counters per email | PASS |

---

## Uncovered Lines Analysis

The 6% uncovered code falls into three categories:

### 1. `database/session.py` (46%) — By Design
The real `get_db()` dependency is overridden in tests with a savepoint-based session fixture. This is intentional and standard practice for integration tests.

### 2. Defensive JWT Validation (auth_services.py, auth_dependency.py)
Lines handling malformed JWT payloads where `sub` is missing, `jti` is missing, or `sub` is not a valid UUID. These branches guard against tampered tokens and would require crafting custom JWTs with missing standard claims. Low risk — PyJWT's own validation catches most real-world tampering.

**Affected lines:**
- `auth_services.py:57,61-62,66` — refresh_access_token: missing sub, invalid UUID
- `auth_services.py:178,182-183,187` — verify_email_token: missing sub, invalid UUID
- `auth_services.py:210,214-215,219` — reset_password: missing sub, invalid UUID
- `auth_dependency.py:30,34-35,39` — get_current_user: missing sub, invalid UUID

### 3. Unused Code Paths (tokens.py, rate_limiter.py)
- `tokens.py:53,108,116,131,146` — `additional_claims` parameter on token creators (never used by app)
- `rate_limiter.py:23-24` — JSON decode error fallback in email key extraction

---

## Test Infrastructure

| Component | Implementation |
|-----------|---------------|
| Database  | Real PostgreSQL (`fastapiapp_test`), no mocks |
| Isolation | Savepoint-per-test with rollback (zero cleanup needed) |
| Email     | `requests.post` patched globally (autouse fixture) |
| Rate limits | Singleton `_hits` dicts cleared before each test |
| Auth helper | `auth_client` fixture: logs in, returns (client, token, user) |

---

## Generated Reports

| Report | Path |
|--------|------|
| This report | `reports/TEST_REPORT.md` |
| Interactive HTML report | `reports/test_report.html` |
| Coverage HTML (per-line) | `reports/coverage_html/index.html` |

---

## Conclusion

### What This Suite Proves

This test suite validates every HTTP endpoint in the application — all 10 routes across user registration, authentication, token management, password reset, email verification, and rate limiting. Every route is tested for its success path, its expected failure modes, and its edge cases. With 67 tests passing and 94% code coverage, the auth system's behavior is well-documented through executable specifications.

The tests are **integration tests by design**. They hit a real PostgreSQL database, exercise real SQLAlchemy queries (including `SELECT ... FOR UPDATE` row locks), and run through the full FastAPI dependency injection chain. The only mock is the outbound Mailgun HTTP call, which is the correct boundary — we verify *that* the app tries to send email and *how* it handles Mailgun failures, without depending on an external service in CI.

### What the Coverage Number Actually Means

The 94% figure is genuine. The 6% uncovered is understood and defensible:

- **`database/session.py` at 46%** is an artifact: the real `get_db` generator is replaced by the test fixture's savepoint-based session. This is standard practice — testing the production `get_db` would mean abandoning test isolation. The function is 8 lines of boilerplate that SQLAlchemy has tested for us.

- **The 17 uncovered lines in `auth_services.py`** are all the same pattern repeated across three functions: `if sub is None`, `try: uuid.UUID(sub) except ValueError`, and `if user is None` after a lookup by a token's `sub` claim. These are defense-in-depth guards against a JWT that passes signature verification but has a missing or malformed `sub` field. In practice, every token the application creates includes a valid UUID `sub`, so these lines can only fire if someone tampers with a token in a way that somehow preserves the HMAC signature — which is cryptographically infeasible with a proper secret. They are still worth keeping in the code, but testing them provides negligible confidence gain.

- **`tokens.py`'s uncovered lines** are the `additional_claims` code paths on `create_refresh_token`, `create_password_reset_token`, and `create_email_verification_token`. The application never passes additional claims to these creators. The parameter exists for future extensibility. If it's ever used, the tests should be extended to match.

### Security Behaviors Verified

The suite goes beyond functional correctness to verify security-critical invariants:

1. **Token revocation works end-to-end.** Logging out blacklists both the access and refresh tokens. Blacklisted JTIs are rejected on `/users/me`, `/auth/refresh`, `/auth/reset-password`, and `/auth/verify-email`.

2. **Password changes invalidate all prior tokens.** Both access and refresh tokens issued before `password_changed_at` are rejected. This means a password reset or change immediately locks out any attacker who stole a session.

3. **Reset codes are single-use.** Using a code clears it from the database. Using a token blacklists its JTI. The second attempt always fails with 400.

4. **Second forgot-password request invalidates the first.** The previous reset code is overwritten and the previous token's JTI is blacklisted. An attacker cannot race the user.

5. **Token JTI must match the user's stored JTI.** Even a cryptographically valid reset token is rejected if its JTI doesn't match `user.password_reset_jti`. This prevents reuse of old tokens that were superseded but not yet expired.

6. **No information leakage.** Forgot-password and resend-verification return 200 regardless of whether the email exists, is verified, or is unknown. The email mock's call count proves whether a real email would have been sent.

7. **Cookie security flags are set.** The refresh token cookie is `httponly` (not accessible to JavaScript) and `samesite=strict` (not sent on cross-origin requests).

8. **The response model doesn't leak internals.** Registration returns `id`, `name`, `email`, and `created_at` — never `password_hash`.

### Test Infrastructure Quality

The fixture design deserves specific mention:

- **Savepoint-based isolation** means each test runs inside a transaction that is rolled back at the end. Tests never leave data behind, never conflict with each other, and never need cleanup logic. This is both faster and more reliable than truncating tables between tests.

- **The `create_test_user` factory** inserts users directly via the ORM, bypassing the API. This means tests for login, reset, and verification don't depend on the registration endpoint working correctly — each test module is independent.

- **Autouse fixtures for email mocking and rate limiter clearing** mean that no test can accidentally send a real email or inherit rate limit state from a previous test. These are the two most common sources of flaky tests in auth systems, and they're eliminated structurally.

### What's Not Tested (and Why That's Acceptable)

- **Concurrent access / race conditions.** The code uses `SELECT ... FOR UPDATE` to prevent double-verification and double-reset. Testing this properly requires multiple simultaneous database connections with controlled timing, which is a different class of test (load/stress testing) and not appropriate for a pytest unit/integration suite.

- **Token expiry in real time.** Expired tokens are tested by crafting JWTs with past `exp` claims. We don't `time.sleep()` through a real 30-minute access token expiry. The PyJWT library's expiry enforcement is well-tested upstream.

- **HTTPS/secure cookie flag.** The `secure` flag on the refresh token cookie is conditional on `ENVIRONMENT == "production"`. The test environment is `"development"`, so the flag is intentionally off. This is correct — testing it would require either mocking the setting or running tests in production mode, both of which test config plumbing rather than security logic.

- **Database migration correctness.** The tests use `Base.metadata.create_all()` to create tables from the ORM models, not Alembic migrations. If an Alembic migration diverges from the model definitions, these tests won't catch it. A separate migration test (applying migrations to an empty database and comparing schema to the ORM) would address this but is outside the scope of this suite.

### Bottom Line

The auth system is tested at the right level of abstraction: real database, real app routing, mocked external services. Every endpoint has happy-path and error-path coverage. Security-critical behaviors (revocation, single-use tokens, session invalidation, info leakage prevention) are explicitly asserted. The uncovered 6% is understood, documented, and low-risk. This suite is ready for CI integration.
