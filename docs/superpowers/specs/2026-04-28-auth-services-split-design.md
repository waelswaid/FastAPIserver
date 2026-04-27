# Slice 2 — Split `auth_services.py` + extract shared helpers

**Date:** 2026-04-28
**Status:** Approved
**Predecessor slice:** [2026-04-27-domain-exceptions-design.md](./2026-04-27-domain-exceptions-design.md)

## Goal

Decompose `app/services/auth_services.py` (351 lines, four tangled concerns) into focused per-domain service modules, and extract two duplicated patterns identified in `refactor_areas.md` (M1, M7).

The split is **behavior-preserving**. No endpoint contract, status code, response body, or audit log message changes. The 184-test suite must remain green at every checkpoint.

## Scope

In scope:
- Split `auth_services.py` into four modules (one retained, three new).
- Extract two helper patterns from M7: `blacklist_jwt` and `upsert_reset_pair`.
- Migrate imports across routes, dependencies, services, and tests.
- Rewrite `admin_services.force_password_reset` to use the shared helper.

Out of scope (deferred to later slices):
- M7 #1 (token-pair creation) — only 2 sites; below the abstraction threshold.
- M3 / M6 — `oauth_service` raw query, direct ORM mutation, FOR UPDATE consistency (slice 7).
- M4 / M12 — magic-string sentinels (`!oauth`, `!invited`), action-type enums (slice 6).
- M11 — refresh-token rotation/family (security slice).
- Any change to `force_password_reset`'s home — stays in `admin_services` (admin domain action with admin audit logging), only its body uses the new helper.

## Module Layout

```
app/services/
├── auth_services.py             # login, refresh, logout
│                                #   jwt_gen, jwt_config, DUMMY_HASH
├── password_service.py          # NEW
│                                # request_password_reset, reset_password,
│                                # reset_password_via_code, validate_reset_code,
│                                # change_password
│                                # ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE,
│                                # ALL_RESET_ACTIONS
│                                # upsert_reset_pair (helper)
├── email_verification_service.py  # NEW
│                                # send_verification_email_for_user,
│                                # resend_verification_email,
│                                # verify_email_token, verify_email_code
│                                # ACTION_EMAIL_VERIFICATION_CODE
├── invite_service.py            # NEW
│                                # validate_invite_code, accept_invite,
│                                # _get_valid_invite
│                                # ACTION_INVITE
├── _token_helpers.py            # NEW
│                                # blacklist_jwt(payload) helper
├── admin_services.py            # imports ACTION_INVITE from invite_service,
│                                # ACTION_PASSWORD_RESET_* + upsert_reset_pair
│                                # from password_service
├── oauth_service.py             # unchanged (still imports jwt_gen
│                                # from auth_services)
└── user_services.py             # imports send_verification_email_for_user
                                 # from email_verification_service
```

## Ownership rules

1. Each new service module owns the action-type constants for its flow.
2. `auth_services.py` retains only login/refresh/logout-adjacent infrastructure that all flows need (`jwt_gen`, `jwt_config`, `DUMMY_HASH`).
3. `_token_helpers.py` (leading underscore) signals an internal cross-service utility module — not a public service.
4. `admin_services.py` imports action constants and helpers from the owning service — does not redefine.

## Helper Definitions

### `app/services/_token_helpers.py`

```python
from datetime import datetime, timezone
from app.repositories.token_blacklist_repository import add_to_blacklist


async def blacklist_jwt(payload: dict) -> None:
    """Blacklist a token by its decoded payload.

    Assumes `jti` and `exp` are present — PyJWT verifies these on decode for
    every token type used here. Callers that need to handle missing fields
    (e.g. logout's strict access-token check) do so themselves.
    """
    jti = payload["jti"]
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
```

**Call sites that adopt this helper:**
- `auth_services.refresh_access_token` — blacklist current refresh during rotation.
- `auth_services.logout` — both the access-token branch and the refresh-token swallow branch.
- `password_service.request_password_reset` — blacklist previous reset JTI.
- `admin_services.force_password_reset` — blacklist previous reset JTI.
- `user_services.delete_own_account` — both access and refresh blacklist sites.

### `app/services/password_service.py` (helper section)

```python
def upsert_reset_pair(
    db: Session,
    user_id: uuid.UUID,
    jti: str,
    jti_expires_at: datetime,
    code: str,
    code_expires_at: datetime,
) -> None:
    """Upsert the JTI + code pending actions for a password reset.
    Caller is responsible for db.commit()."""
    upsert_action(db, user_id, ACTION_PASSWORD_RESET_JTI, jti, jti_expires_at, commit=False)
    upsert_action(db, user_id, ACTION_PASSWORD_RESET_CODE, code, code_expires_at, commit=False)
```

**Call sites:**
- `password_service.request_password_reset`
- `admin_services.force_password_reset`

## Import Migration

| File | Change |
|---|---|
| `app/api/dependencies/auth_dependency.py` | unchanged — `jwt_gen` still imported from `auth_services` |
| `app/services/oauth_service.py` | unchanged — `jwt_gen` still imported from `auth_services` |
| `app/api/routes/auth_routes.py` | split current single import: keeps `user_login, refresh_access_token, logout, jwt_gen` from `auth_services`; adds imports from `password_service`, `email_verification_service`, `invite_service` |
| `app/services/admin_services.py` | `from app.services.invite_service import ACTION_INVITE`; `from app.services.password_service import ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE, upsert_reset_pair`; rewrite `force_password_reset` body to use helper |
| `app/services/user_services.py` | `from app.services.email_verification_service import send_verification_email_for_user`; `from app.services._token_helpers import blacklist_jwt` (used by `delete_own_account`'s two blacklist sites) |
| `tests/test_email_verification.py` | import `ACTION_EMAIL_VERIFICATION_CODE` from `email_verification_service` |
| `tests/test_forgot_password.py`, `tests/test_reset_password.py` | import `ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI` from `password_service` |
| `tests/test_me.py`, `tests/test_rbac.py`, `tests/test_token_refresh.py` | unchanged — `jwt_gen` import path is stable |

## Test Strategy

The split is structural. Existing tests cover the moved functions; they must continue to pass. No new test files are created.

**Per-task verification:**
- After moving functions for one domain (e.g., password reset), run the relevant test file (`tests/test_reset_password.py`, `tests/test_forgot_password.py`, `tests/test_change_password.py`).
- After helper extraction, run the union of test files that exercise the helper's call sites.

**Final verification:**
- Full `pytest` suite must pass (184 tests) before the slice is closed.

**Helpers are not separately unit-tested** — they are mechanical extractions of code already covered by integration tests. Adding redundant unit tests would be ceremony.

## Risks and Mitigations

- **Risk:** Circular imports between new services.
  **Mitigation:** Each new service imports only from `_token_helpers`, repos, and utilities. Cross-service imports are limited to constants (one direction: `admin_services` → `password_service` / `invite_service`). No service imports from another service for behavior.

- **Risk:** A test references a moved symbol via the old path.
  **Mitigation:** `grep -rn "from app.services.auth_services"` after each task; full suite at end.

- **Risk:** Subtle behavior change in `logout`'s refresh-token swallow when adopting `blacklist_jwt`.
  **Mitigation:** The helper is called *inside* the existing `try/except TokenError` block. Missing `jti`/`exp` would raise `KeyError`, not `TokenError`, so the existing `if rt_jti is not None and rt_exp is not None` guard is preserved at the call site (the helper is only invoked when both are present).

## Acceptance Criteria

- [ ] Three new service modules exist with the listed function bodies and constants.
- [ ] `_token_helpers.py` exists and is used at all listed call sites.
- [ ] `upsert_reset_pair` exists in `password_service.py` and is used by both `password_service.request_password_reset` and `admin_services.force_password_reset`.
- [ ] `auth_services.py` contains only login, refresh, logout, `jwt_gen`, `jwt_config`, and `DUMMY_HASH` — no action-type constants (those move to their owning services).
- [ ] All 184 existing tests pass.
- [ ] `grep -rn "from app.services.auth_services"` shows only references to symbols still owned by `auth_services` (`jwt_gen`, login/refresh/logout).
