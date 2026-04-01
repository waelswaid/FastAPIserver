# The Gatekeeper: A Story of Authentication, Trust, and Tokens

---

## Preface

This is the story of a service whose sole purpose is to answer one question: *"Are you who you say you are?"*

Built for the developer who wants a production-ready authentication backend without inheriting the complexity of a full identity platform, **auth-system** is a FastAPI microservice that handles the entire lifecycle of user identity — from the moment someone registers, through the verification of their email, the daily ritual of logging in, the inevitable forgotten password, and the administrative oversight that keeps it all in check.

It is written for backend developers who understand HTTP but want to see how authentication *should* be built — with asymmetric cryptography, atomic rate limiting, row-level database locks, and the kind of paranoia that comes from knowing that auth is the one thing you cannot get wrong.

---

## Table of Contents

1. **The Front Gate** — `app/api/routes/`
2. **The Bouncers** — `app/api/dependencies/`
3. **The Brain** — `app/services/`
4. **The Archive** — `app/repositories/`
5. **The Blueprint** — `app/models/`
6. **The Contracts** — `app/schemas/`
7. **The Vault** — `app/utils/`
8. **The Foundation** — `app/core/`
9. **The Migration Trail** — `migrations/`
10. **The Proving Grounds** — `tests/`
11. **The Packaging** — `Dockerfile`, `entrypoint.sh`, `docker-compose`
12. **The Pipeline** — `.github/workflows/ci.yml`

---

## Chapter 1: The Front Gate

**`app/api/routes/`** — *Where every request begins its journey*

Four routers stand at the entrance, each guarding a different corridor:

**`auth_routes.py`** is the busiest gate. It handles login, logout, token refresh, password reset, email verification, Google OAuth, and user invitations. Every auth operation flows through here. The login endpoint alone wears three rate limiters and an account lockout guard — a testament to how aggressively the outside world knocks on this particular door.

**`user_routes.py`** is quieter. Four endpoints: create an account, view yourself, update yourself, delete yourself. The full lifecycle of a user's self-service experience, from `POST /users/create` to `DELETE /users/me`.

**`admin_routes.py`** is the restricted wing. Every endpoint here requires the `admin` role. List users, change roles, disable accounts, force password resets, send invitations. The `admin_dependency = require_role("admin")` line at the top is the velvet rope.

**`health_routes.py`** is the simplest — a single `GET /health` that pings the database and Redis, returning `healthy`, `degraded`, or `unhealthy`. The canary in the coal mine.

The routes never think. They validate input, call a service, and format the response. This is by design — the CLAUDE.md constitution explicitly forbids business logic in routes.

*Connects to: Chapter 2 (dependencies are injected here), Chapter 3 (services are called here)*

---

## Chapter 2: The Bouncers

**`app/api/dependencies/`** — *The guards who inspect every visitor before they enter*

**`auth_dependency.py`** is the identity checker. `get_current_user()` extracts the Bearer token, decodes it, checks if it's been blacklisted in Redis, verifies the user still exists in the database, confirms the account isn't disabled, and — critically — checks whether the token was issued *before* the user's password or role was last changed. A token minted before a password change is a dead token, no matter its expiry. The `require_role()` factory produces specialized guards: pass it `"admin"` and it returns a dependency that rejects anyone without that role.

**`rate_limiter.py`** is the crowd controller. It implements a sliding window counter using a Redis Lua script — atomic, race-condition-proof, and precise. Fifteen limiter instances are pre-configured, each with its own threshold: 5/hr for registration, 10/hr for login per email, 30/hr for login per IP, 40/hr for OAuth. The `lockout_limiter` is special — it doesn't just count requests, it counts *failures*, locking an account after 10 bad passwords for 15 minutes. If Redis goes down, the limiters fail open — availability over security in that edge case, a deliberate tradeoff.

*Connects to: Chapter 1 (injected into routes via `Depends()`), Chapter 8 (reads Redis connection)*

---

## Chapter 3: The Brain

**`app/services/`** — *Where decisions are made*

This is where the business logic lives, and it is the thickest chapter in the book.

**`auth_services.py`** is the protagonist. `user_login()` verifies credentials, checks email verification status, checks disabled status, and mints a token pair. `refresh_access_token()` validates the refresh token, checks the blacklist, verifies no password or role change has occurred since issuance, blacklists the old refresh token, and issues a fresh pair — token rotation in action. `logout()` blacklists both tokens. `change_password()` updates the hash and blacklists the current tokens. Every method logs an audit event: `audit: event=login`, `audit: event=logout`, `audit: event=password_changed`. These breadcrumbs are the service's memory.

**`oauth_service.py`** handles the Google OAuth dance. `get_google_auth_url()` builds the consent URL. `google_callback()` exchanges the authorization code for a Google access token, fetches the user's profile, then resolves identity through three cases: existing OAuth link (just log in), existing email match (link the account), or new user (create everything). OAuth-only users get `password_hash="!oauth"` — a sentinel value that no Argon2id hash will ever produce, effectively making password login impossible for them.

**`user_services.py`** handles registration and account deletion. **`admin_services.py`** handles the admin operations — role changes, account disable/enable, forced resets, and invitations. Invited users are created with `password_hash="!invited"`, another sentinel, and receive an email with a time-limited code to set their credentials.

*Connects to: Chapter 4 (all database access goes through repositories), Chapter 7 (uses JWT and hashing utilities)*

---

## Chapter 4: The Archive

**`app/repositories/`** — *The librarians who read and write the records*

Repositories are deliberately unintelligent. They execute queries and return results. No validation, no business rules, no HTTP exceptions.

**`user_repository.py`** provides `create_user`, `find_user_by_email`, `find_by_id_for_update` (with `FOR UPDATE` row locking), `update_password`, `verify_user`, `update_role`, and `delete_user`. The `_for_update` variant is critical — it acquires a database-level lock on the row, preventing race conditions when two concurrent requests try to verify the same email or reset the same password.

**`pending_action_repository.py`** manages ephemeral records: password reset codes, email verification codes, invite codes. `upsert_action` overwrites any existing action of the same type for the same user — you can't have two pending password resets. `cleanup_expired_actions` runs at startup, sweeping away stale records.

**`token_blacklist_repository.py`** is Redis-only. `add_to_blacklist(jti, expiry)` stores a revoked token's JTI with a TTL matching its remaining lifetime — once the token would have expired naturally, Redis automatically evicts the blacklist entry. Zero wasted memory.

**`oauth_account_repository.py`** links users to OAuth providers. The unique constraint on `(provider, provider_user_id)` ensures one Google account can only link to one local user.

*Connects to: Chapter 5 (queries against these models), Chapter 8 (database sessions and Redis clients)*

---

## Chapter 5: The Blueprint

**`app/models/`** — *The shape of the data*

Three SQLAlchemy models define the schema:

**`User`** — `id` (UUID), `email` (unique, indexed), `password_hash`, `first_name`, `last_name`, `role` (default `"user"`), `is_verified`, `is_disabled`, `created_at`, `password_changed_at`, `role_changed_at`. The two timestamp columns are the secret weapon of token invalidation — any token issued before these timestamps is automatically rejected by the auth dependency.

**`PendingAction`** — `user_id`, `action_type`, `code`, `expires_at`. A unique constraint on `(user_id, action_type)` means each user can have at most one pending action of each type. This table is the staging area for email verification, password reset, and invitation codes.

**`OAuthAccount`** — `user_id`, `provider`, `provider_user_id`. The bridge between local identity and external identity providers.

*Connects to: Chapter 9 (Alembic migrations evolve these schemas over time)*

---

## Chapter 6: The Contracts

**`app/schemas/`** — *The language spoken at the border*

Pydantic models define what goes in and what comes out:

- `LoginRequest` — email + password
- `TokenResponse` — access_token + token_type
- `UserCreate` — email, password, first_name, last_name
- `UserRead` — the public face of a user (no password hash)
- `ForgotPasswordRequest`, `ResetPasswordRequest`, `ChangePasswordRequest` — the password lifecycle
- `ChangeRoleRequest`, `DisableUserRequest`, `InviteUserRequest`, `AcceptInviteRequest` — admin operations

These schemas are the API's contract with the outside world. FastAPI uses them for automatic validation, serialization, and OpenAPI documentation.

*Connects to: Chapter 1 (routes declare these as parameter types and return types)*

---

## Chapter 7: The Vault

**`app/utils/`** — *The cryptographic machinery*

**`tokens.py`** — The `JWTUtility` class wraps PyJWT with RS256 asymmetric signing. The private key signs tokens; the public key verifies them. This separation matters in a microservice world — you can distribute the public key to consumer services for local token validation without exposing the signing key. Every token carries a `jti` (JWT ID) — a UUID that enables individual token revocation via the blacklist.

**`security/password_hash.py`** — Argon2id hashing via `pwdlib`. Two functions: `hash_password()` and `verify_password()`. Argon2id is the current winner of the Password Hashing Competition — memory-hard, resistant to GPU attacks, and the recommended choice for new applications.

**`email.py`** — Sends password reset and verification emails through the Mailgun API. Template-based, with codes embedded in links.

*Connects to: Chapter 3 (services call these utilities for token and password operations)*

---

## Chapter 8: The Foundation

**`app/core/`** — *The infrastructure everything else stands on*

**`config.py`** — A Pydantic `Settings` class that loads environment variables. Database URL, RSA keys, token expiry times, rate limit thresholds, Mailgun credentials, Google OAuth secrets, lockout parameters — everything configurable, nothing hardcoded.

**`redis.py`** — An async Redis client wrapper with connection lifecycle management. If Redis is unavailable at startup, the system logs a warning and continues — rate limiting degrades gracefully rather than crashing the service.

**`logging.py`** — Structured JSON logging with correlation IDs. Every request gets a UUID stored in a `contextvars.ContextVar`, and every log line within that request carries the same ID. When you're reading logs from a distributed system, this is how you follow a single request across services.

**`app/main.py`** — The FastAPI application factory. Registers routes, configures CORS, sets up the middleware pipeline (request logging, rate limit headers), and manages startup/shutdown lifecycle (Redis initialization, expired action cleanup).

*Connects to: Everything — this is the bedrock*

---

## Chapter 9: The Migration Trail

**`migrations/`** — *The geological record*

Alembic migrations track every schema evolution: the initial `users` and `pending_actions` tables, the addition of `oauth_accounts`, the `is_disabled` column, the movement of token blacklisting from a database table to Redis. Each migration is a chapter in the database's history, and `alembic upgrade head` in the Docker entrypoint ensures the schema is always current before the application starts.

*Connects to: Chapter 5 (migrations evolve the models)*

---

## Chapter 10: The Proving Grounds

**`tests/`** — *Where trust is earned*

21+ test files, each focused on a single feature: `test_login.py`, `test_registration.py`, `test_email_verification.py`, `test_reset_password.py`, `test_change_password.py`, `test_logout.py`, `test_token_refresh.py`, `test_rbac.py`, `test_rate_limiting.py`, `test_admin_management.py`, `test_account_deletion.py`, `test_google_oauth.py`.

Tests run against a real PostgreSQL database — no SQLite substitutes. Each test runs inside a transaction that rolls back at the end, giving every test a clean slate without the cost of rebuilding the database. Redis is mocked via `fakeredis` with Lua scripting support, so rate limiting logic is tested faithfully.

`conftest.py` is the backstage crew — fixtures for the test client, database sessions, pre-built users with known credentials, and admin users for RBAC tests.

*Connects to: Everything — tests exercise every layer*

---

## Chapter 11: The Packaging

**`Dockerfile`** — A multi-stage build. The builder stage installs dependencies; the runtime stage copies only what's needed, runs as a non-root `appuser`, and exposes port 8000.

**`entrypoint.sh`** — Two lines that matter: `alembic upgrade head` (migrate the database) then `exec uvicorn app.main:app` (start the server). Migrations run before every boot, making deployments zero-touch.

**`docker-compose.example.yml`** — PostgreSQL, Redis, and the auth service, wired together on a Docker network.

*Connects to: Chapter 8 (config reads from environment variables set in Docker)*

---

## Chapter 12: The Pipeline

**`.github/workflows/ci.yml`** — Two jobs run on every push:

**Lint** — `flake8` checks for syntax errors, complexity violations (max 10), and style issues (max line length 127). Warnings don't block the build; errors do.

**Test** — Spins up a PostgreSQL 17 service container, installs dependencies, runs `pytest` with coverage reporting. If the tests don't pass, the code doesn't merge.

*Connects to: Chapter 10 (runs the test suite), Chapter 11 (mirrors the production environment)*

---

## Epilogue

What makes this codebase interesting is not any single feature — it's the discipline of the layering.

Routes never touch the database. Services never construct SQL. Repositories never raise HTTP exceptions. Utilities never know about the request. Each layer has a single reason to exist, and the boundaries are enforced by convention and by the project's own CLAUDE.md constitution.

The security model is particularly well-considered. Asymmetric JWT signing means consumer services can validate tokens without knowing the signing key. Token blacklisting uses Redis TTLs aligned to token expiry, so revocation entries self-clean. Password and role changes automatically invalidate all existing tokens through timestamp comparison — no need to enumerate and revoke them. Rate limiting uses atomic Lua scripts to prevent race conditions in the counter itself. Row-level database locks prevent concurrent verification or reset attempts from corrupting state.

Where could it go next? The invitation system and OAuth linking suggest a multi-tenant future. The `validate-token` endpoint is already built for service-to-service communication. The health check is ready for orchestrator probes. The foundation is here for the service to grow — but the Gatekeeper's job will always be the same: *verify who you are, and make sure you're allowed in.*
