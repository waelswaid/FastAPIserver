# Auth Roadmap — Remaining Work

## Current state
- [X] JWT utility (`app/utils/tokens.py`)
- [X] JWT config in `config.py` and `.env`
- [X] `find_user_by_email` / `find_user_by_id` return `Optional[User]`
- [X] `LoginRequest` and `TokenResponse` schemas
- [X] `auth_services.py` — login logic
- [X] `POST /api/auth/login` — working, tested
- [X] `get_current_user` dependency (`app/api/dependencies/auth_dependency.py`)

---

## Step 1 — Protected test endpoint

Add a temporary route to `auth_routes.py` to verify `get_current_user` works before touching real routes.

- [ ] add `GET /api/auth/me` to `auth_routes.py`
- [ ] inject `current_user: User = Depends(get_current_user)`
- [ ] return the user's `id` and `email`

**Test it:**
- [ ] no token → expect 401
- [ ] invalid/malformed token → expect 401
- [ ] expired token → expect 401
- [ ] valid token → expect 200 with user info

Do not move on until all four cases pass.

---

## Step 2 — Protect task routes

Once the test endpoint is confirmed working, apply the dependency to real routes in `task_routes.py`.

- [ ] protect `GET /api/tasks/get`
- [ ] protect `POST /api/tasks/create`
- [ ] protect `POST /api/tasks/complete`

Each route gets `current_user: User = Depends(get_current_user)` added to its parameters.

**Test each:**
- [ ] request without token → 401
- [ ] request with valid token → original behavior unchanged

---

## Step 3 — Update test script

Extend `test_auth.py` to cover the new protected behavior.

- [ ] test `/api/auth/me` with valid token → 200
- [ ] test `/api/auth/me` with no token → 401
- [ ] test `/api/auth/me` with bad token → 401
- [ ] test a task route with valid token → 200
- [ ] test a task route with no token → 401

---

## Step 4 — Fix remaining layer violation

`create_user` in `user_repository.py` still raises `HTTPException` directly — that's an HTTP concern leaking into the repo layer.

- [ ] change `create_user` to raise a plain `ValueError` (or return `None`) on duplicate email
- [ ] move the 409 `HTTPException` into `user_services.py` or `user_routes.py`

---

## Step 5 — Security sanity check

Before calling Phase 1 done:

- [ ] plaintext password never stored or returned
- [ ] JWT secret comes from `.env`, not hardcoded anywhere
- [ ] expired tokens are rejected (verify via test or manual check)
- [ ] invalid tokens are rejected
- [ ] all protected routes return 401 without a valid token
- [ ] token payload contains only `sub`, `type`, `iat`, `exp` — no sensitive data

---

## Phase 1 is done when

- [ ] user can register
- [ ] user can login and receive a JWT
- [ ] `get_current_user` dependency works correctly
- [ ] `/api/auth/me` protected endpoint works
- [ ] all three task routes are protected
- [ ] layer responsibilities are clean (no HTTP concerns in repo layer)
