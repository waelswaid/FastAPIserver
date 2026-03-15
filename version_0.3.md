# FastAPI App — V0.3 Changes

This document covers everything added on top of the architecture described in `version_0.2.md`.
V0.3 pivots the app into a dedicated **authentication and authorization system**, removing the task layer entirely and building out a full JWT-based auth flow.

---

## Removed Files

All task-related code was removed as the app now focuses solely on auth:

| Removed File | Was |
|---|---|
| `app/api/routes/task_routes.py` | Task HTTP routes |
| `app/services/task_services.py` | Task business logic |
| `app/repositories/task_repository.py` | Task DB queries |
| `app/models/task.py` | Task ORM model |
| `app/schemas/task_model.py` | Task Pydantic schemas |

---

## New Files

| File | Purpose |
|---|---|
| `app/utils/tokens.py` | `JWTConfig` dataclass + `JWTUtility` class — creates and decodes access and refresh tokens |
| `app/schemas/login_request.py` | `LoginRequest` schema — validates email + password on login |
| `app/schemas/token_response.py` | `TokenResponse` schema — shape of the JSON response after login or refresh |
| `app/services/auth_services.py` | Auth business logic — `user_login`, `refresh_access_token`, `logout` |
| `app/api/routes/auth_routes.py` | Auth HTTP routes — `/login`, `/refresh`, `/logout` |
| `app/api/dependencies/auth_dependency.py` | `get_current_user` dependency — extracts and validates a Bearer token on protected routes |
| `app/models/token_blacklist.py` | `TokenBlacklist` ORM model — stores revoked token IDs |
| `app/repositories/token_blacklist_repository.py` | `add_to_blacklist`, `is_blacklisted` — DB operations for token revocation |

---

## New Database Table

### `token_blacklist`

| Column | Type | Notes |
|---|---|---|
| `jti` | `VARCHAR` | Primary key — unique ID embedded in every JWT |
| `expires_at` | `TIMESTAMPTZ` | When the token naturally expires — safe to clean up after this |

---

## JWT Utility — `utils/tokens.py`

Two dataclasses/classes handle all token logic:

### `JWTConfig`
A configuration container holding the secret key, algorithm, and expiry durations. Changing the secret key invalidates all existing tokens.

### `JWTUtility`
All token creation and decoding goes through this class via a private `_create_token()` helper:

```
JWTUtility
├── create_access_token(subject)   →  short-lived token (default: 30 min)
├── create_refresh_token(subject)  →  long-lived token  (default: 1 day)
├── decode_access_token(token)     →  decodes + asserts type == "access"
└── decode_refresh_token(token)    →  decodes + asserts type == "refresh"
```

Every token payload contains:

| Claim | Meaning |
|---|---|
| `sub` | Subject — the user's UUID |
| `type` | `"access"` or `"refresh"` — prevents one type being used as the other |
| `iat` | Issued at timestamp |
| `exp` | Expiry timestamp |
| `jti` | Unique token ID (UUID4) — used for revocation |

---

## Changes to Existing Files

### `app/core/config.py`
Added four new settings loaded from `.env`:

| Setting | Default | Purpose |
|---|---|---|
| `JWT_SECRET_KEY` | — | Signs and verifies all tokens |
| `JWT_ALGORITHM` | `"HS256"` | Signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `ENVIRONMENT` | `"development"` | Controls cookie `secure` flag — set to `"production"` in prod |

### `app/api/routes/user_routes.py`
Added the `GET /api/users/me` protected endpoint (see endpoints table below).

### `app/main.py`
- Removed `tasks_router`
- Registered `auth_router` under `/api`

---

## New Endpoints

| Method | Path | Auth required | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | Verify credentials, return access token + set refresh cookie |
| POST | `/api/auth/refresh` | No (cookie) | Exchange refresh cookie for a new access token |
| POST | `/api/auth/logout` | Yes | Revoke access token, clear refresh cookie |
| GET | `/api/users/me` | Yes | Return the authenticated user's profile |

---

## Architecture Diagrams

### 1. Login Flow — `POST /api/auth/login`

```
Client
  │
  │  POST /api/auth/login  { "email": "...", "password": "..." }
  ▼
auth_routes.py
  │  Parses body into LoginRequest (Pydantic validates email + password length)
  │  Calls user_login(db, login_data)
  ▼
auth_services.py  →  user_repository.find_user_by_email()
  │  User not found or password wrong  →  401 Invalid Credentials
  │  Password verified via verify_password()
  │  jwt_gen.create_access_token(user.id)   →  short-lived JWT
  │  jwt_gen.create_refresh_token(user.id)  →  long-lived JWT
  │  Returns (access_token, refresh_token) tuple
  ▼
auth_routes.py
  │  response.set_cookie("refresh_token", httponly=True, ...)
  │  Returns JSON: { "access_token": "...", "token_type": "bearer" }
  ▼
Client
  │  Stores access_token in memory
  └  Browser stores refresh_token cookie automatically (JS cannot read it)
```

---

### 2. Protected Route — `GET /api/users/me`

```
Client
  │
  │  GET /api/users/me
  │  Authorization: Bearer <access_token>
  ▼
user_routes.py
  │  Depends(get_current_user) — triggers the dependency
  ▼
auth_dependency.get_current_user()
  │  oauth2_scheme extracts the Bearer token from the Authorization header
  │  jwt_gen.decode_access_token(token)
  │    └─ Invalid / expired  →  401
  │  is_blacklisted(db, jti)
  │    └─ Token revoked      →  401
  │  uuid.UUID(payload["sub"])
  │  find_user_by_id(db, user_id)
  │    └─ User not found     →  401
  │  Returns User ORM object
  ▼
user_routes.get_me()
  │  Receives User directly — no extra DB call needed
  │  FastAPI serializes User → UserRead schema
  ▼
Client
  └  Response: { "id": "...", "name": "...", "email": "...", "created_at": "..." }
```

---

### 3. Refresh Flow — `POST /api/auth/refresh`

```
Client
  │
  │  POST /api/auth/refresh
  │  (refresh_token cookie sent automatically by browser)
  ▼
auth_routes.py
  │  Cookie(...) extracts refresh_token from the request cookies
  │  Cookie missing  →  401 No refresh token provided
  │  Calls refresh_access_token(db, refresh_token)
  ▼
auth_services.refresh_access_token()
  │  jwt_gen.decode_refresh_token(token)
  │    └─ Invalid / expired / wrong type  →  401
  │  Extracts user UUID from payload["sub"]
  │  find_user_by_id(db, user_id)
  │    └─ User not found  →  401
  │  jwt_gen.create_access_token(user.id)
  │  Returns TokenResponse
  ▼
Client
  └  Response: { "access_token": "...", "token_type": "bearer" }
```

---

### 4. Logout / Token Revocation — `POST /api/auth/logout`

```
Client
  │
  │  POST /api/auth/logout
  │  Authorization: Bearer <access_token>
  ▼
auth_routes.py
  │  oauth2_scheme extracts the Bearer token
  │  Calls logout(db, token)
  ▼
auth_services.logout()
  │  jwt_gen.decode_access_token(token)
  │    └─ Invalid  →  401
  │  Extracts jti and exp from payload
  │  add_to_blacklist(db, jti, expires_at)
  │    └─ Inserts row into token_blacklist table
  ▼
auth_routes.py
  │  response.delete_cookie("refresh_token")
  │  Returns 204 No Content
  ▼
Client
  └  Access token is now dead. Refresh cookie is cleared.
     Any future request with the old token → 401 (blacklist check in get_current_user)
```

---

### 5. Token Blacklist Check (inside every protected route)

```
Every request to a protected route
  │
  ▼
get_current_user()
  │
  ├─ decode_access_token(token)
  │     └─ Expired or tampered  →  401
  │
  ├─ is_blacklisted(db, jti)        ← DB lookup on token_blacklist table
  │     └─ jti found in table  →  401
  │
  ├─ find_user_by_id(db, user_id)
  │     └─ User deleted  →  401
  │
  └─ Returns User  →  route handler proceeds
```

---

## Security Design Decisions

| Decision | Reason |
|---|---|
| Refresh token in HTTP-only cookie | JavaScript cannot read it — XSS attacks cannot steal it |
| `secure` cookie flag tied to `ENVIRONMENT` | Cookie is HTTPS-only in production; works over HTTP in local dev |
| `jti` claim on every token | Enables individual token revocation without invalidating all tokens |
| Blacklist stores `expires_at` | Entries can be safely pruned after the token would have expired anyway |
| Refresh token type check | A refresh token cannot be used as an access token — `decode_access_token` rejects it |
