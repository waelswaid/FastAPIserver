# auth-system

A production-shaped authentication backend in FastAPI — JWT (RS256), refresh-token rotation, Google OAuth, RBAC, Argon2id, Redis rate limiting (Lua sliding window), token revocation, and an instrumented dev client for end-to-end observability.

Designed to drop in as the auth tier of a larger application, or to stand alone behind any frontend.

> **[See the dev client in action →](docs/screenshots.md)** — Activity log, Token panel, and Codes panel walkthrough.

---

## 30-second start

```bash
make bootstrap        # one-time: copies compose/env, generates RSA keys
make backend-up       # FastAPI + Postgres + Redis (hot reload)
make frontend-up      # Vite dev client at http://localhost:5173
make logs             # tail backend; verification/reset codes print here in dev
```

Backend at `http://localhost:8000` (interactive docs at `/docs`). Then open `http://localhost:5173` and start exercising flows from the **Public** tab.

> No Mailgun account needed in development — the email layer prints codes to the backend log instead. See *Dev mode* below.

`make` requires Git Bash or WSL on Windows. Without `make`: `choco install make` or `winget install GnuWin32.Make`.

---

## At a glance

```
   ┌─────────────────┐      ┌──────────────────────────────────────┐      ┌──────────────┐
   │  dev-client     │ ───▶ │  FastAPI                             │ ───▶ │  PostgreSQL  │
   │  (Vite + React) │      │  ─ RS256 JWT (access + refresh)      │      │  + Alembic   │
   │  Inspect tab:   │      │  ─ Argon2id, RBAC, account lockout   │      └──────────────┘
   │   Token / API   │      │  ─ Redis-backed rate limit + revoke  │      ┌──────────────┐
   │   Activity log  │      │  ─ Google OAuth, invites, reset      │ ───▶ │    Redis     │
   └─────────────────┘      └──────────────────┬───────────────────┘      │ rate limit + │
                                               │                          │  blacklist   │
                                               ▼                          └──────────────┘
                                        ┌──────────────┐
                                        │   Mailgun    │
                                        │ (dev → log)  │
                                        └──────────────┘
```

### API endpoints

#### Health

| Method | Path      | Auth | Description                                 |
|--------|-----------|------|---------------------------------------------|
| GET    | `/health` | No   | Database + Redis connectivity check         |

#### Users (`/api`)

| Method | Path          | Auth   | Rate Limited     | Description                                 |
|--------|---------------|--------|------------------|---------------------------------------------|
| POST   | `/users`      | No     | 5/hr per IP      | Register a new user                         |
| GET    | `/users/me`   | Bearer | No               | Get authenticated user profile              |
| PATCH  | `/users/me`   | Bearer | No               | Update profile (first/last name)            |
| DELETE | `/users/me`   | Bearer | 5/hr per IP      | Delete own account (requires password)      |

#### Auth (`/api/auth`)

| Method | Path                    | Auth   | Rate Limited                                                | Description                                        |
|--------|-------------------------|--------|-------------------------------------------------------------|----------------------------------------------------|
| POST   | `/login`                | No     | 10/hr per IP+email · 30/hr per IP · lockout after N failures | Returns access + sets refresh-token cookie         |
| POST   | `/refresh`              | Cookie | 30/hr per IP                                                | Refresh access token                               |
| POST   | `/logout`               | Bearer | No                                                          | Revoke tokens, clear cookie                        |
| POST   | `/change-password`      | Bearer | 5/hr per IP                                                 | Change password (requires current)                 |
| POST   | `/forgot-password`      | No     | 5/hr per IP+email                                           | Send password reset email                          |
| GET    | `/reset-password`       | No     | 10/hr per IP                                                | Validate reset code                                |
| POST   | `/reset-password`       | No     | 10/hr per IP                                                | Reset password with code or token                  |
| POST   | `/resend-verification`  | No     | 5/hr per IP+email                                           | Resend verification email                          |
| GET    | `/verify-email`         | No     | 10/hr per IP                                                | Verify email via code from link                    |
| POST   | `/verify-email`         | No     | 10/hr per IP                                                | Verify email via JWT token                         |
| GET    | `/validate-token`       | Bearer | No                                                          | Validate token, return user info (svc-to-svc)      |
| GET    | `/accept-invite`        | No     | 10/hr per IP                                                | Validate invite code                               |
| POST   | `/accept-invite`        | No     | 10/hr per IP                                                | Activate invited account (code + name + password)  |

#### Google OAuth (`/api/auth`)

| Method | Path                | Auth | Rate Limited  | Description                            |
|--------|---------------------|------|---------------|----------------------------------------|
| GET    | `/google`           | No   | 20/hr per IP  | Redirect to Google consent screen      |
| GET    | `/google/callback`  | No   | No            | Handle Google redirect, issue tokens   |

#### Admin (`/api/admin`) — `admin` role required

| Method | Path                                       | Rate Limited  | Description                                          |
|--------|--------------------------------------------|---------------|------------------------------------------------------|
| GET    | `/users/`                                  | No            | List users (`?role=` filter, pagination)             |
| PATCH  | `/users/{user_id}/role`                    | No            | Change a user's role                                 |
| PATCH  | `/users/{user_id}/status`                  | No            | Disable or enable a user account                     |
| POST   | `/users/{user_id}/force-password-reset`    | 20/hr per IP  | Send password reset email to a user                  |
| POST   | `/users/invite`                            | 20/hr per IP  | Invite a user by email                               |

---

## What's in the box

**Authentication**
- RS256 JWT — 15-min access tokens + 1-day refresh tokens stored as `httponly` cookies; key rotation is a config swap
- Google OAuth — auto-links existing accounts by email, creates new users on first login (auto-verified)
- RBAC — `user` / `admin` role, embedded in the JWT for fast local checks and re-verifiable via `/validate-token`
- Email verification, password reset, change-password, self-serve account deletion, admin-issued invitations

**Security & integrity**
- Argon2id password hashing (pwdlib)
- Account lockout after N failed logins (Redis counter, configurable cooldown)
- Sliding-window rate limiting per IP and per email (atomic Lua script, no race windows)
- Token revocation — JWTs blacklisted in Redis on logout; password and role changes invalidate all in-flight tokens
- Row-level locks (`WITH FOR UPDATE`) on verification, reset, and invite acceptance to prevent code-reuse races
- Email-existence non-disclosure on reset/verification flows (identical responses for known and unknown addresses)

**Operability**
- `/health` endpoint with per-dependency up/down status (Postgres, Redis)
- Structured audit logging — `audit: event=<name> user_id=<id> …` lines for every auth-relevant action
- Dev mode — `ENVIRONMENT=development` makes verification, reset, and invite codes print to the backend log instead of calling Mailgun, so every flow is exercisable without external dependencies
- Tests run against a real PostgreSQL with per-test transaction rollback; Redis is `fakeredis`-backed so they stay fast and hermetic
- One-command Docker workflow with hot reload (`make backend-up`) plus an opt-in dev client (`make frontend-up`)
- GitHub Actions CI — lint + tests + coverage on every push

---

## Dev client — what makes this repo different

The `dev-client/` is a small Vite + React app that drives every backend flow from a browser, with a built-in **Inspect** tab for observability ([screenshots](docs/screenshots.md)):

- **Token** — every JWT that flows through the client is captured in a table. Click a row to expand the decoded header and payload claims, watch the live `exp` countdown, and (on the active token) hit `/api/auth/validate-token` to compare the local-decoded view against the server's view side-by-side.
- **Activity** — a chronological log of every API call the client makes, with status-class filters, path search, click-to-expand request/response bodies, and an `email` column showing whose token authorized each call. Passwords and tokens are redacted at write time before they ever reach `sessionStorage`.
- **Codes** — in dev, the verification/reset/invite codes that the email layer emits show up here in real time, with click-to-copy. Removes the need to tail backend logs while developing flows.
- **Health** — one-click `/health` with a per-dependency up/down breakdown.

This isn't a UI for end users — it's a debugging surface I built to make the auth flows legible while developing the backend. It also persists across the OAuth redirect roundtrip, so you can trace login flows that leave and return to the page.

---

## Deeper dives

<details>
<summary><strong>Tech stack</strong></summary>

| Layer       | Technology                                       |
|-------------|--------------------------------------------------|
| Framework   | FastAPI 0.135, Uvicorn                           |
| Database    | PostgreSQL, SQLAlchemy 2.0, Alembic              |
| Auth        | PyJWT (RS256), pwdlib (Argon2id)                 |
| Cache/queue | Redis 7 (sliding-window Lua, blacklist, lockout) |
| OAuth       | Google OAuth 2.0                                 |
| Email       | Mailgun (production) · console log (dev)         |
| Tests       | pytest, httpx, fakeredis, real Postgres          |
| CI          | GitHub Actions — flake8 + pytest + coverage      |
| Dev client  | Vite, React 19, TypeScript, Tailwind             |

</details>

<details>
<summary><strong>Local development without Docker</strong></summary>

Prerequisites: Python 3.14+, PostgreSQL, Redis (optional in dev).

```bash
git clone https://github.com/waelswaid/auth-system.git
cd auth-system

python -m venv venv
source venv/bin/activate          # or venv\Scripts\activate on Windows

pip install -r requirements.txt
cp .env.example .env
# fill in DATABASE_URL, JWT keys (see below), and any optional values

alembic upgrade head
uvicorn app.main:app --reload
```

For the dev client, in another shell:

```bash
cd dev-client
npm install
npm run dev
```

Redis is optional — rate limiting and token blacklist degrade silently if it's not running. Google OAuth is optional — the "Sign in with Google" button returns 503 unless credentials are configured.

</details>

<details>
<summary><strong>Generating RSA keys</strong></summary>

The system signs JWTs with RS256 (asymmetric), so leaks of the verification key don't grant the ability to forge tokens.

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Paste the contents of each file into `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` in `.env`. `make bootstrap` does this automatically on first run.

</details>

<details>
<summary><strong>Dev mode (no Mailgun)</strong></summary>

When `ENVIRONMENT=development`, the three email helpers in `app/utils/email.py` log the code/link to the backend logger and skip the Mailgun HTTP call. Codes look like:

```
audit: event=dev_email type=password_reset recipient=user@example.com code=<uuid> link=...
```

Watch them with `make logs`, then paste into the matching dev-client form to complete the flow. The same codes are also visible in **Inspect → Codes** in the dev client (auto-refresh, copy-to-clipboard, no terminal needed) — backed by an in-memory ring buffer exposed at `GET /api/dev/codes`. Both the console-log branch and the dev endpoint are gated by `settings.ENVIRONMENT != "production"`; the route is only registered in non-production environments and the handler re-checks the gate. Production deployments must set `ENVIRONMENT=production`.

</details>

<details>
<summary><strong>RBAC details</strong></summary>

Users have a `role` field (`user` by default, `admin` available). The role is:
- Embedded in the JWT at issuance for fast local checks
- Returned by `GET /api/auth/validate-token` for authoritative live lookup from consumer services

When a role changes, `role_changed_at` is set and all existing tokens for that user are invalidated (same pattern as password changes — invalidation is by `iat < role_changed_at`).

Bootstrap the first admin:

```bash
make admin EMAIL=admin@example.com
# or, outside docker:
python -m scripts.promote_admin admin@example.com
```

</details>

<details>
<summary><strong>Google OAuth</strong></summary>

`GET /api/auth/google` issues a redirect to Google's consent screen with a CSRF-bound state cookie. `GET /api/auth/google/callback` validates the state, exchanges the code, and either:

- Links the Google account to an existing user matched by email, or
- Creates a new user (auto-verified, no password — they must run password reset to set one).

On success, an access token is appended to `OAUTH_FRONTEND_REDIRECT_URL` (or the first `CORS_ORIGINS` entry) as a query parameter; the dev client picks it up at `/oauth-callback?token=…`. The refresh token is set as an `httponly` cookie just like password login.

Endpoints return 503 cleanly when Google credentials aren't configured, so the rest of the system stays exercisable without them.

</details>

<details>
<summary><strong>Rate limiting & lockout internals</strong></summary>

Rate limiters use a Redis sliding-window counter implemented as a Lua script (atomic, no read-modify-write races). Keys include both the IP and, where applicable, the email to make per-account limits resilient to NAT'd users. Failures are recorded in a separate `lockout:<email>` counter; on hitting the threshold the limiter returns 429 with `Retry-After`.

If Redis is unreachable, the limiters fail open with a warning log — local dev keeps working, and production should monitor this signal.

</details>

<details>
<summary><strong>Testing</strong></summary>

```bash
make test                # pytest in container, creates test DB on first run
make test-cov            # with coverage

# or locally:
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

Tests use a real PostgreSQL with per-test transaction rollback (no DB pollution). Redis is mocked with `fakeredis`. Email sending is patched at the function boundary, so the same fixtures cover both the production and dev-console branches.

</details>

<details>
<summary><strong>Make targets</strong></summary>

```
make bootstrap         First-run setup (compose, .env, RSA keys)
make backend-up        Start backend stack (hot reload)
make frontend-up       Start the dev client on :5173
make frontend-restart  Restart dev client (pick up vite.config or new deps)
make down              Stop and remove all containers
make logs              Tail backend logs (dev codes print here)
make restart           Restart the backend
make build             Rebuild backend image without starting
make test              Run pytest in container
make test-cov          Run pytest with coverage
make shell             Shell into the backend container
make psql              psql into Postgres
make redis             redis-cli into Redis
make migrate           alembic upgrade head
make admin EMAIL=…     Promote a user to admin
make help              List all targets
```

Run prod-style (no override applied):

```bash
docker compose -f docker-compose.example.yml up --build
```

</details>

<details>
<summary><strong>Environment variables</strong></summary>

See `.env.example` for the full template. Required at minimum: `DATABASE_URL`, `REDIS_URL` (optional in dev), `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `ENVIRONMENT`. Mailgun and Google OAuth values are optional.

</details>

---

## Repository layout

```
app/
├── api/              # routes + dependencies (auth, users, admin, health)
├── core/             # config, logging, redis client
├── database/         # session + engine
├── models/           # SQLAlchemy — one file per model
├── repositories/     # DB access — no business logic
├── schemas/          # Pydantic request/response models
├── services/         # business logic — split by concern (auth, password, invite, email-verification, oauth, admin)
├── utils/            # JWT, password hashing, email
└── exceptions.py     # domain errors
dev-client/           # Vite + React — exercises every flow + Inspect tab
migrations/           # Alembic
tests/                # pytest — real Postgres, fakeredis
.github/workflows/    # CI
```

The service-layer pattern is enforced: routes → services → repositories → DB. Routes never touch the database directly; repositories never hold business logic.
