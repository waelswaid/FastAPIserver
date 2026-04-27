# Slice 2 Implementation Plan — Split `auth_services.py`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose `app/services/auth_services.py` into four focused modules and extract two duplicated patterns (`blacklist_jwt`, `upsert_reset_pair`) without changing any externally visible behavior.

**Architecture:** Behavior-preserving structural refactor. Each task moves one cohesive group of functions into a new module, then updates every importer in the same commit so the suite stays green between commits. Helpers live in `_token_helpers.py` (cross-service) and `password_service.py` (domain-local).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, PyJWT (RS256), pytest. Test DB: PostgreSQL (`fastapiapp_test`, password `postgres`).

**Reference spec:** `docs/superpowers/specs/2026-04-28-auth-services-split-design.md`

**TDD note:** This is a behavior-preserving refactor. The 184 existing tests cover every moved function. "Test-first" does not apply — the verification gate at every task is *the existing suite must still pass*. No new tests are added in this slice.

**Test command:** `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`

**Working branch:** `master` (continuing slice 1's pattern; user authorized direct commits).

---

## File Structure (after slice)

```
app/services/
├── _token_helpers.py            (new — Task 1)
├── auth_services.py             (shrunk — login/refresh/logout, jwt_gen, DUMMY_HASH)
├── invite_service.py            (new — Task 2)
├── email_verification_service.py(new — Task 3)
├── password_service.py          (new — Task 4)
├── admin_services.py            (modified — Tasks 2, 4)
├── user_services.py             (modified — Task 3)
└── oauth_service.py             (unchanged)

tests/
├── test_email_verification.py   (modified — Task 3)
├── test_forgot_password.py      (modified — Task 4)
├── test_reset_password.py       (modified — Task 4)
└── (others unchanged — jwt_gen import path is stable)
```

---

## Task 1: Add `_token_helpers.py` with `blacklist_jwt`

**Purpose:** Land the shared helper as a pure addition before any move. No call site adopts it yet — Task 5 does that. This keeps the diff small and verifiable.

**Files:**
- Create: `app/services/_token_helpers.py`

- [ ] **Step 1: Create the file**

```python
from datetime import datetime, timezone
from app.repositories.token_blacklist_repository import add_to_blacklist


async def blacklist_jwt(payload: dict) -> None:
    """Blacklist a token by its decoded payload.

    Assumes `jti` and `exp` are present — PyJWT verifies these on decode for
    every token type used here. Callers that need to handle missing fields
    (e.g. logout's strict access-token check) do so themselves before calling
    this helper.
    """
    jti = payload["jti"]
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
```

- [ ] **Step 2: Run full suite**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`
Expected: 184 passed.

- [ ] **Step 3: Commit**

```bash
git add app/services/_token_helpers.py
git commit -m "feat(services): add _token_helpers.blacklist_jwt (slice 2 task 1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Extract `invite_service.py`

**Purpose:** Smallest of the three new domain services. Move first to validate the move-and-rewire pattern before tackling larger ones.

**Files:**
- Create: `app/services/invite_service.py`
- Modify: `app/services/auth_services.py` (remove invite functions and `ACTION_INVITE`)
- Modify: `app/api/routes/auth_routes.py:13-18` (import path for `accept_invite`, `validate_invite_code`)
- Modify: `app/services/admin_services.py:10-12` (import `ACTION_INVITE` from new module)

- [ ] **Step 1: Create `app/services/invite_service.py`**

```python
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.user_repository import set_invited_user_profile
from app.repositories.pending_action_repository import (
    find_user_by_action_code_for_update, delete_action,
)
from app.utils.security.password_hash import hash_password

logger = logging.getLogger(__name__)

ACTION_INVITE = "invite"


def _get_valid_invite(db: Session, code: str):
    result = find_user_by_action_code_for_update(db, code, ACTION_INVITE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invite has already been accepted")

    return action, user


def validate_invite_code(db: Session, code: str) -> None:
    _get_valid_invite(db, code)


def accept_invite(db: Session, code: str, first_name: str, last_name: str, password: str) -> None:
    action, user = _get_valid_invite(db, code)
    set_invited_user_profile(db, user, first_name, last_name, hash_password(password), commit=False)
    delete_action(db, action, commit=False)
    db.commit()
    logger.info("audit: event=invite_accepted user_id=%s email=%s", user.id, user.email)
```

- [ ] **Step 2: Remove the moved code from `app/services/auth_services.py`**

Delete the following block (current lines 311–339):

```python
ACTION_INVITE = "invite"


def _get_valid_invite(db: Session, code: str):
    result = find_user_by_action_code_for_update(db, code, ACTION_INVITE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invite has already been accepted")

    return action, user


def validate_invite_code(db: Session, code: str) -> None:
    _get_valid_invite(db, code)


def accept_invite(db: Session, code: str, first_name: str, last_name: str, password: str) -> None:
    action, user = _get_valid_invite(db, code)
    set_invited_user_profile(db, user, first_name, last_name, hash_password(password), commit=False)
    delete_action(db, action, commit=False)
    db.commit()
    logger.info("audit: event=invite_accepted user_id=%s email=%s", user.id, user.email)
```

- [ ] **Step 3: Update `app/api/routes/auth_routes.py` imports**

Change lines 13–18 from:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password, verify_email_token, resend_verification_email,
    verify_email_code, reset_password_via_code, validate_reset_code, change_password,
    accept_invite, validate_invite_code,
)
```

to:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password, verify_email_token, resend_verification_email,
    verify_email_code, reset_password_via_code, validate_reset_code, change_password,
)
from app.services.invite_service import accept_invite, validate_invite_code
```

- [ ] **Step 4: Update `app/services/admin_services.py` imports**

Change line 10–12 from:

```python
from app.services.auth_services import (
    jwt_gen, ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE, ACTION_INVITE,
)
```

to:

```python
from app.services.auth_services import (
    jwt_gen, ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE,
)
from app.services.invite_service import ACTION_INVITE
```

- [ ] **Step 5: Run full suite**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`
Expected: 184 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/invite_service.py app/services/auth_services.py app/api/routes/auth_routes.py app/services/admin_services.py
git commit -m "refactor(services): extract invite_service from auth_services (slice 2 task 2)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Extract `email_verification_service.py`

**Purpose:** Move all four email-verification functions (JWT and code variants) plus `ACTION_EMAIL_VERIFICATION_CODE` into their own module.

**Files:**
- Create: `app/services/email_verification_service.py`
- Modify: `app/services/auth_services.py` (remove four functions and one constant)
- Modify: `app/api/routes/auth_routes.py:13-18` (move three function imports)
- Modify: `app/services/user_services.py:6` (move `send_verification_email_for_user` import)
- Modify: `tests/test_email_verification.py:4` (move `ACTION_EMAIL_VERIFICATION_CODE` import)

- [ ] **Step 1: Create `app/services/email_verification_service.py`**

```python
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
import requests as http_requests

from app.repositories.user_repository import find_user_by_email, find_user_by_id_for_update, verify_user
from app.repositories.pending_action_repository import (
    upsert_action, find_user_by_action_code_for_update, delete_action,
)
from app.repositories.token_blacklist_repository import is_blacklisted, add_to_blacklist
from app.exceptions import TokenError
from app.models.user import User
from app.services.auth_services import jwt_gen
from app.utils.email import send_verification_email

logger = logging.getLogger(__name__)

ACTION_EMAIL_VERIFICATION_CODE = "email_verification_code"


def send_verification_email_for_user(db: Session, user: User) -> None:
    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.email_verification_token_expiry_minutes
    )
    send_verification_email(user.email, code)
    upsert_action(db, user.id, ACTION_EMAIL_VERIFICATION_CODE, code, expires_at)


def resend_verification_email(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or user.is_verified:
        return

    try:
        send_verification_email_for_user(db, user)
    except http_requests.RequestException as exc:
        logger.error("Failed to send verification email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")


async def verify_email_token(db: Session, token: str) -> None:
    try:
        payload = jwt_gen.decode_email_verification_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
        raise HTTPException(status_code=400, detail="Verification link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user_id, user.email)


def verify_email_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_EMAIL_VERIFICATION_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    action, user = result

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    delete_action(db, action, commit=False)
    verify_user(db, user, commit=False)
    db.commit()
    logger.info("audit: event=email_verified user_id=%s email=%s", user.id, user.email)
```

- [ ] **Step 2: Remove moved code from `app/services/auth_services.py`**

Delete:
- `ACTION_EMAIL_VERIFICATION_CODE = "email_verification_code"` (currently line 30)
- `send_verification_email_for_user` (currently 172–178)
- `resend_verification_email` (currently 181–190)
- `verify_email_token` (currently 193–224)
- `verify_email_code` (currently 264–280)

Also remove now-unused imports from `auth_services.py` if no remaining function references them:
- `verify_user` from `app.repositories.user_repository`
- `delete_action` from `app.repositories.pending_action_repository`
- `find_user_by_action_code_for_update` from `app.repositories.pending_action_repository` (Task 4 will re-check this — `password_service` still uses it)
- `send_verification_email` from `app.utils.email`

Be conservative: leave imports in place that are still used by remaining functions. Audit after deletion.

- [ ] **Step 3: Update `app/api/routes/auth_routes.py` imports**

After Task 2's edit, lines 13–18 read:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password, verify_email_token, resend_verification_email,
    verify_email_code, reset_password_via_code, validate_reset_code, change_password,
)
from app.services.invite_service import accept_invite, validate_invite_code
```

Change to:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password,
    reset_password_via_code, validate_reset_code, change_password,
)
from app.services.email_verification_service import (
    verify_email_token, resend_verification_email, verify_email_code,
)
from app.services.invite_service import accept_invite, validate_invite_code
```

- [ ] **Step 4: Update `app/services/user_services.py` imports**

Change line 6 from:

```python
from app.services.auth_services import send_verification_email_for_user, jwt_gen
```

to:

```python
from app.services.auth_services import jwt_gen
from app.services.email_verification_service import send_verification_email_for_user
```

- [ ] **Step 5: Update `tests/test_email_verification.py` imports**

Change line 4 from:

```python
from app.services.auth_services import jwt_gen, ACTION_EMAIL_VERIFICATION_CODE
```

to:

```python
from app.services.auth_services import jwt_gen
from app.services.email_verification_service import ACTION_EMAIL_VERIFICATION_CODE
```

- [ ] **Step 6: Run full suite**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`
Expected: 184 passed.

- [ ] **Step 7: Commit**

```bash
git add app/services/email_verification_service.py app/services/auth_services.py app/api/routes/auth_routes.py app/services/user_services.py tests/test_email_verification.py
git commit -m "refactor(services): extract email_verification_service from auth_services (slice 2 task 3)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Extract `password_service.py` with `upsert_reset_pair` helper

**Purpose:** Move all password-related flows (JWT reset, code reset, validate code, change-password) into one module and introduce the `upsert_reset_pair` helper. Rewrite `admin_services.force_password_reset` to use the helper.

**Files:**
- Create: `app/services/password_service.py`
- Modify: `app/services/auth_services.py` (remove four functions, two constants, `ALL_RESET_ACTIONS`)
- Modify: `app/api/routes/auth_routes.py` (move five function imports)
- Modify: `app/services/admin_services.py` (move action-constant import; rewrite `force_password_reset` body)
- Modify: `tests/test_forgot_password.py:8` and `tests/test_reset_password.py:4`

- [ ] **Step 1: Create `app/services/password_service.py`**

```python
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session
import requests as http_requests

from app.repositories.user_repository import (
    find_user_by_email, find_user_by_id_for_update, update_password,
)
from app.repositories.pending_action_repository import (
    upsert_action, find_action_by_user_and_type,
    find_user_by_action_code_for_update, delete_actions_for_user,
)
from app.repositories.token_blacklist_repository import is_blacklisted, add_to_blacklist
from app.exceptions import TokenError
from app.models.user import User
from app.services.auth_services import jwt_gen
from app.utils.email import send_password_reset_email
from app.utils.security.password_hash import verify_password, hash_password

logger = logging.getLogger(__name__)

ACTION_PASSWORD_RESET_JTI = "password_reset_jti"
ACTION_PASSWORD_RESET_CODE = "password_reset_code"

ALL_RESET_ACTIONS = [ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE]


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


async def request_password_reset(db: Session, email: str) -> None:
    user = find_user_by_email(db, email)
    if user is None or not user.is_verified or user.password_hash == "!oauth":
        return

    code = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_gen.config.password_reset_token_expiry_minutes
    )

    reset_token = jwt_gen.create_password_reset_token(str(user.id))
    new_payload = jwt_gen.decode_password_reset_token(reset_token)
    new_jti = new_payload.get("jti")
    new_jti_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    prev_jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if prev_jti_action is not None:
        await add_to_blacklist(prev_jti_action.code, prev_jti_action.expires_at)

    upsert_reset_pair(db, user.id, new_jti, new_jti_expires_at, code, expires_at)
    db.commit()

    try:
        send_password_reset_email(user.email, code)
    except http_requests.RequestException as exc:
        logger.error("Failed to send password reset email: %s", exc)
        raise HTTPException(status_code=503, detail="Unable to send email. Please try again later.")

    logger.info("audit: event=password_reset_requested user_id=%s email=%s", user.id, user.email)


async def reset_password(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt_gen.decode_password_reset_token(token)
    except TokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    jti = payload.get("jti")
    if jti is None or await is_blacklisted(jti):
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = find_user_by_id_for_update(db, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    jti_action = find_action_by_user_and_type(db, user.id, ACTION_PASSWORD_RESET_JTI)
    if jti_action is None or jti_action.code != jti:
        raise HTTPException(status_code=400, detail="Reset link has already been used")

    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user_id, user.email)


def reset_password_via_code(db: Session, code: str, new_password: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_reset user_id=%s email=%s", user.id, user.email)


def validate_reset_code(db: Session, code: str) -> None:
    result = find_user_by_action_code_for_update(db, code, ACTION_PASSWORD_RESET_CODE)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    action, user = result

    if action.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if user.password_hash == "!oauth":
        raise HTTPException(status_code=400, detail="Password change is not available for OAuth accounts. Set a password first.")
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    update_password(db, user, hash_password(new_password), commit=False)
    delete_actions_for_user(db, user.id, ALL_RESET_ACTIONS, commit=False)
    db.commit()
    logger.info("audit: event=password_changed user_id=%s email=%s", user.id, user.email)
```

- [ ] **Step 2: Remove moved code from `app/services/auth_services.py`**

Delete:
- `ACTION_PASSWORD_RESET_JTI = "password_reset_jti"` (currently line 29)
- `ACTION_PASSWORD_RESET_CODE = "password_reset_code"` (currently line 31)
- `ALL_RESET_ACTIONS = [...]` (currently line 33)
- `request_password_reset` (currently 139–169)
- `reset_password` (currently 227–261)
- `reset_password_via_code` (currently 283–296)
- `change_password` (currently 299–308)
- `validate_reset_code` (currently 342–350)

After deletion, audit imports at the top of `auth_services.py` and remove any that are no longer used. The remaining file should import only what login/refresh/logout still need:
- `find_user_by_email`, `find_user_by_id` from `user_repository` (login uses these; verify which exact names)
- `add_to_blacklist`, `is_blacklisted` from `token_blacklist_repository` (refresh + logout use these)
- `verify_password`, `hash_password` from `password_hash` (login uses verify; `DUMMY_HASH` uses hash)
- `JWTConfig`, `JWTUtility` from `tokens`
- `settings`, `TokenResponse`, `LoginRequest`, `User`, `HTTPException`, `Session`
- `datetime`, `timezone`, `uuid`, `logging`, `TokenError` (logout's swallow)
- `requests as http_requests`: only used by removed functions — safe to remove if no remaining function uses it

Verify against the actual remaining function bodies after deletion. Don't guess — re-read the file.

- [ ] **Step 3: Update `app/api/routes/auth_routes.py` imports**

After Task 3 the imports are:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
    request_password_reset, reset_password,
    reset_password_via_code, validate_reset_code, change_password,
)
from app.services.email_verification_service import (
    verify_email_token, resend_verification_email, verify_email_code,
)
from app.services.invite_service import accept_invite, validate_invite_code
```

Change to:

```python
from app.services.auth_services import (
    user_login, refresh_access_token, logout, jwt_gen,
)
from app.services.password_service import (
    request_password_reset, reset_password,
    reset_password_via_code, validate_reset_code, change_password,
)
from app.services.email_verification_service import (
    verify_email_token, resend_verification_email, verify_email_code,
)
from app.services.invite_service import accept_invite, validate_invite_code
```

- [ ] **Step 4: Update `app/services/admin_services.py` imports and rewrite `force_password_reset`**

After Task 2, lines 10–13 read:

```python
from app.services.auth_services import (
    jwt_gen, ACTION_PASSWORD_RESET_JTI, ACTION_PASSWORD_RESET_CODE,
)
from app.services.invite_service import ACTION_INVITE
```

Change to:

```python
from app.services.auth_services import jwt_gen
from app.services.invite_service import ACTION_INVITE
from app.services.password_service import (
    ACTION_PASSWORD_RESET_JTI, upsert_reset_pair,
)
```

(Note: `ACTION_PASSWORD_RESET_CODE` is no longer needed in `admin_services` because `force_password_reset` will call `upsert_reset_pair` rather than two separate `upsert_action` calls. Verify by reading `admin_services.py` after the change — if any other line still references `ACTION_PASSWORD_RESET_CODE`, keep it imported.)

Then rewrite the body of `force_password_reset` (currently lines 89–119). Replace the two `upsert_action` calls (currently lines 108–109) with a single helper call:

Before (lines 108–109):

```python
    upsert_action(db, user.id, ACTION_PASSWORD_RESET_JTI, new_jti, new_jti_expires_at, commit=False)
    upsert_action(db, user.id, ACTION_PASSWORD_RESET_CODE, code, expires_at, commit=False)
```

After:

```python
    upsert_reset_pair(db, user.id, new_jti, new_jti_expires_at, code, expires_at)
```

Verify after the edit that `upsert_action` is no longer imported in `admin_services.py` (line 6 currently imports it). If `force_password_reset` and `invite_user` were the only consumers and `invite_user` still uses `upsert_action`, keep the import. Audit imports.

- [ ] **Step 5: Update test imports**

`tests/test_forgot_password.py:8`:

```python
from app.services.auth_services import ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI
```

→

```python
from app.services.password_service import ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI
```

`tests/test_reset_password.py:4`:

```python
from app.services.auth_services import jwt_gen, ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI
```

→

```python
from app.services.auth_services import jwt_gen
from app.services.password_service import ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI
```

- [ ] **Step 6: Run full suite**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`
Expected: 184 passed.

- [ ] **Step 7: Commit**

```bash
git add app/services/password_service.py app/services/auth_services.py app/api/routes/auth_routes.py app/services/admin_services.py tests/test_forgot_password.py tests/test_reset_password.py
git commit -m "refactor(services): extract password_service from auth_services + upsert_reset_pair helper (slice 2 task 4)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Adopt `blacklist_jwt` helper at all call sites

**Purpose:** Now that the file split is done and stable, replace the duplicated decode-jti-exp-blacklist boilerplate at every call site with the helper from Task 1.

**Call sites to update:**

1. `app/services/auth_services.py:106` — `refresh_access_token` blacklisting current refresh during rotation.
2. `app/services/auth_services.py` (logout) — both the access-token branch and the refresh-token swallow branch.
3. `app/services/password_service.py` — `request_password_reset` previous-JTI blacklist.
4. `app/services/admin_services.py` — `force_password_reset` previous-JTI blacklist.
5. `app/services/user_services.py:42-58` — `delete_own_account`'s two blacklist sites.

**Files:**
- Modify: `app/services/auth_services.py`
- Modify: `app/services/password_service.py`
- Modify: `app/services/admin_services.py`
- Modify: `app/services/user_services.py`

**Important nuance:** at sites 3 and 4, the existing code blacklists by passing the *stored action's* `code` and `expires_at`, not by decoding a token. Those are NOT applications of `blacklist_jwt` — they call `add_to_blacklist` with raw values, no JWT involved. **Skip sites 3 and 4.** This is a correction to the spec's call-site list — re-reading the code shows those sites don't fit the helper's signature.

**Revised call sites that adopt `blacklist_jwt`:**

1. `auth_services.refresh_access_token` (current line 106): replace `await add_to_blacklist(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))` with `await blacklist_jwt(payload)`.
2. `auth_services.logout` access-token branch (current lines 118–124): the existing `if jti is None or exp is None: raise HTTPException(401)` guard stays; the subsequent `add_to_blacklist` call becomes `await blacklist_jwt(payload)`. (`exp` is not used after the helper call, so the local `exp = payload.get("exp")` at line 119 can be removed if it's not used elsewhere — verify.)
3. `auth_services.logout` refresh-token swallow (current lines 127–136): inside the existing `if rt_jti is not None and rt_exp is not None:` guard, replace the two-line decode-and-blacklist with `await blacklist_jwt(rt_payload)`.
4. `user_services.delete_own_account` access branch (lines 42–48): inside the existing `if jti and exp:` guard, replace `add_to_blacklist(...)` with `await blacklist_jwt(payload)`.
5. `user_services.delete_own_account` refresh branch (lines 50–58): inside the existing `if rt_jti and rt_exp:` guard, replace `add_to_blacklist(...)` with `await blacklist_jwt(rt_payload)`.

- [ ] **Step 1: Update `app/services/auth_services.py`**

Add import at top:

```python
from app.services._token_helpers import blacklist_jwt
```

In `refresh_access_token`, replace (current line 106):

```python
    await add_to_blacklist(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))
```

with:

```python
    await blacklist_jwt(payload)
```

In `logout`, the access-token block (current lines 118–125) becomes:

```python
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    await blacklist_jwt(payload)
    logger.info("audit: event=logout user_id=%s", payload.get("sub"))
```

(The `expires_at = ...` local at the old line 123 disappears — `blacklist_jwt` computes it internally.)

In `logout`, the refresh-token swallow block (current lines 127–136) becomes:

```python
    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti is not None and rt_exp is not None:
                await blacklist_jwt(rt_payload)
        except TokenError:
            pass
```

After these edits, audit `auth_services.py` imports — `add_to_blacklist` may no longer be used directly. If `is_blacklisted` is still used (it is, by `refresh_access_token` line ~93), keep that import. Remove `add_to_blacklist` from the import line if it has no remaining usage.

- [ ] **Step 2: Update `app/services/user_services.py`**

Add import at top:

```python
from app.services._token_helpers import blacklist_jwt
```

In `delete_own_account`, replace lines 42–48:

```python
    try:
        payload = jwt_gen.decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            await add_to_blacklist(jti, datetime.fromtimestamp(exp, tz=timezone.utc))
    except TokenError:
        pass
```

with:

```python
    try:
        payload = jwt_gen.decode_access_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            await blacklist_jwt(payload)
    except TokenError:
        pass
```

And lines 50–58:

```python
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

with:

```python
    if refresh_token is not None:
        try:
            rt_payload = jwt_gen.decode_refresh_token(refresh_token)
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti and rt_exp:
                await blacklist_jwt(rt_payload)
        except TokenError:
            pass
```

After these edits, `add_to_blacklist` is no longer used directly in `user_services.py` — remove it from line 5's import.

Also: line 11 imports `from datetime import datetime, timezone`. The `datetime.fromtimestamp` calls are gone after this task. Check whether any remaining code in `user_services.py` uses `datetime` or `timezone`. If not, remove the import. (Currently the only references are inside the blacklist sites being replaced.)

- [ ] **Step 3: Run full suite**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest`
Expected: 184 passed.

- [ ] **Step 4: Commit**

```bash
git add app/services/auth_services.py app/services/user_services.py
git commit -m "refactor(services): adopt blacklist_jwt helper across call sites (slice 2 task 5)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Final verification

**Purpose:** Confirm slice acceptance criteria and that no stragglers remain.

- [ ] **Step 1: Full pytest run**

Run: `DATABASE_URL='postgresql://postgres:postgres@localhost:5432/fastapiapp_test' python -m pytest -v`
Expected: 184 passed.

- [ ] **Step 2: Grep audit — no stale `auth_services` symbols**

Run: `git grep -n "from app.services.auth_services"`

Expected output: every match is one of these symbols:
- `jwt_gen`
- `user_login`
- `refresh_access_token`
- `logout`

If any match imports `ACTION_*`, `request_password_reset`, `reset_password`, `verify_email_token`, `accept_invite`, `send_verification_email_for_user`, `change_password`, etc., it's a leftover — fix it.

- [ ] **Step 3: Grep audit — `auth_services.py` is shrunken**

Run: `wc -l app/services/auth_services.py`

Expected: significantly less than 351 lines (target ≈130 lines for login + refresh + logout + module setup).

- [ ] **Step 4: Confirm helpers are used**

Run: `git grep -n "blacklist_jwt"`
Expected: definition in `_token_helpers.py`, plus 5 call sites (auth_services 3×, user_services 2×).

Run: `git grep -n "upsert_reset_pair"`
Expected: definition in `password_service.py`, plus 2 call sites (`password_service.request_password_reset`, `admin_services.force_password_reset`).

- [ ] **Step 5: No commit needed for verification.**

If grep audits surface issues, fix them in a follow-up commit and re-run the suite.

---

## Self-Review Checklist (filled by author)

- **Spec coverage:** Every section of the spec maps to a task — module layout (1–4), helpers (1, 4), import migration (2–4), call-site adoption (5), verification (6).
- **Placeholder scan:** No TBD/TODO/`add error handling`. Every step has concrete code or a concrete command.
- **Type consistency:** Helper signatures match across spec and plan. Function names match (`blacklist_jwt`, `upsert_reset_pair`).
- **Call-site correction:** During plan-writing I caught that the spec's claim "`request_password_reset` / `force_password_reset` adopt `blacklist_jwt`" was wrong — those sites blacklist a stored action's code, not a decoded JWT. Plan task 5 explicitly skips them. The spec's mitigation note in Risks says callers handle their own None checks, which is consistent.
