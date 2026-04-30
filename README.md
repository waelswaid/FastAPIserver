# FastAPI Auth System

An authentication API built with FastAPI. Provides user registration, email verification, JWT-based authentication, password reset, Google OAuth, admin management, and Redis-backed rate limiting out of the box.

Use it as a standalone auth backend or as the foundation for your own application.

## Features

- **JWT authentication** — RS256 asymmetric tokens, access tokens (30 min) + refresh tokens (httponly cookie, 1 day)
- **Google OAuth** — login with Google, auto-links existing accounts by email, creates new users on first login
- **RBAC** — role-based access control (user/admin), role embedded in JWT and validate-token
- **Email verification** — code-based and token-based flows via Mailgun
- **Password reset** — secure reset flow with expiring codes
- **Change password** — authenticated password change with token invalidation
- **Account deletion** — self-service account deletion with password confirmation
- **Account lockout** — automatic lockout after 10 failed login attempts (15 min cooldown)
- **Admin endpoints** — role management, user listing, disable/enable accounts, force password reset, invite users
- **User invitations** — admin-initiated invite flow with expiring codes
- **Rate limiting** — Redis sliding window counter (Lua script), per-IP and per-email
- **Token revocation** — Redis blacklist + password/role-change invalidation
- **Argon2id** password hashing
- **Row-level locks** on verification and reset to prevent race conditions
- **Health check** — `/health` endpoint with database and Redis connectivity status
- **Structured logging** — JSON logs with correlation IDs for request tracing
- **CI pipeline** — GitHub Actions with linting (flake8) and tests (pytest + coverage)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.135 + Uvicorn |
| Database | PostgreSQL + SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | PyJWT (RS256 — asymmetric RSA keys) |
| Hashing | Argon2id (pwdlib) |
| Email | Mailgun API |
| Rate Limiting | Redis (sliding window, Lua script) |
| OAuth | Google OAuth 2.0 |
| Testing | pytest + httpx + fakeredis |

## Quickstart

### Option 1: Docker (recommended)

```bash
cp docker-compose.example.yml docker-compose.yml
cp .env.example .env
# Edit .env with your secrets (RSA keys, Mailgun credentials, Google OAuth, etc.)
docker compose up -d --build
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Option 2: Local development

**Prerequisites:** Python 3.14+, PostgreSQL, Redis

```bash
git clone https://github.com/waelswaid/auth-system.git
cd auth-system

python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database URL, secrets, etc.

alembic upgrade head
uvicorn app.main:app --reload
```

### Generating RSA keys

The system uses RS256 (asymmetric RSA) for JWT signing. Generate a keypair:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Then paste the contents into `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` in your `.env` file.

### Docker dev workflow

`docker-compose.override.yml` is auto-merged when you run `docker compose up`. It swaps the app service over to `Dockerfile.dev` (full deps, no source COPY), mounts the source as a volume, and runs uvicorn with `--reload`. The prod Dockerfile and `docker-compose.example.yml` are untouched.

A `Makefile` at the repo root wraps the common commands. First-run setup (copies compose/env files, generates RSA keys into `.env`):

```bash
make bootstrap
make backend-up       # start backend (hot reload)
make frontend-up      # add the Vite dev-client at http://localhost:5173
make logs             # watch dev codes printed by ENVIRONMENT=development
make test             # run pytest in the container (creates test DB on first run)
make admin EMAIL=you@example.com
make down             # stop and remove all containers (backend + frontend)
make help             # list all targets
```

Run prod-style (no override applied, no Make involvement):

```bash
docker compose -f docker-compose.example.yml up --build
```

(`make` requires Git Bash or WSL on Windows. If `make` isn't installed: `choco install make` or `winget install GnuWin32.Make`.)

## Local development end-to-end

To exercise every flow locally without Mailgun:

1. Copy `.env.example` to `.env` (subsequent steps fill in values).
2. Start Postgres and create the database referenced by `DATABASE_URL`.
3. Generate JWT keys (see "Generating RSA keys" above) and paste into `.env`.
4. In `.env`, set `ENVIRONMENT=development`. The three email helpers in `app/utils/email.py` will then log verification/reset/invite codes to the backend console instead of calling Mailgun.
5. Run migrations and start the backend:
   ```bash
   alembic upgrade head
   uvicorn app.main:app --reload
   ```
6. In another terminal, start the dev client:
   ```bash
   cd dev-client
   npm install
   npm run dev
   ```
7. Open http://localhost:5173. Trigger flows from the client UI. When the backend prints a code (e.g. `audit: event=dev_email type=password_reset recipient=... code=<uuid> link=...`), copy the code into the matching client form to complete the flow.

Redis is optional in dev — rate limiting and token blacklist degrade silently if it isn't running. Google OAuth is optional — the "Sign in with Google" button returns 503 unless credentials are configured.

## API Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check (database + Redis status) |

### Users (`/api`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| POST | `/users` | No | 5/hr per IP | Register a new user |
| GET | `/users/me` | Bearer | No | Get authenticated user profile |
| PATCH | `/users/me` | Bearer | No | Update profile (first_name, last_name) |
| DELETE | `/users/me` | Bearer | 5/hr per IP | Delete own account (requires password) |

### Auth (`/api/auth`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| POST | `/login` | No | 10/hr per IP+email, 30/hr per IP, lockout after 10 failures | Login, returns access + refresh tokens |
| POST | `/refresh` | Cookie | 30/hr per IP | Refresh access token |
| POST | `/logout` | Bearer | No | Revoke tokens and clear cookie |
| POST | `/change-password` | Bearer | 5/hr per IP | Change password (requires current password) |
| POST | `/forgot-password` | No | 5/hr per IP+email | Send password reset email |
| GET | `/reset-password` | No | 10/hr per IP | Validate reset code from email |
| POST | `/reset-password` | No | 10/hr per IP | Reset password with code or token |
| POST | `/resend-verification` | No | 5/hr per IP+email | Resend verification email |
| GET | `/verify-email` | No | 10/hr per IP | Verify email via code from email link |
| POST | `/verify-email` | No | 10/hr per IP | Verify email via JWT token |
| GET | `/validate-token` | Bearer | No | Validate token and return user info (service-to-service) |
| GET | `/accept-invite` | No | 10/hr per IP | Validate invite code |
| POST | `/accept-invite` | No | 10/hr per IP | Activate invited account (code + name + password) |

### Google OAuth (`/api/auth`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| GET | `/google` | No | 20/hr per IP | Redirects to Google consent screen |
| GET | `/google/callback` | No | No | Handles Google redirect, issues tokens |

On first login, if the email matches an existing account, the Google account is linked automatically. If the email is new, a new user is created (auto-verified, cannot password-login unless they set one via password reset).

### Admin (`/api/admin`)

All admin endpoints require the `admin` role.

| Method | Path | Rate Limited | Description |
|--------|------|--------------|-------------|
| GET | `/users/` | No | List users (optional `?role=` filter, pagination) |
| PATCH | `/users/{user_id}/role` | No | Change a user's role (`user` or `admin`) |
| PATCH | `/users/{user_id}/status` | No | Disable or enable a user account |
| POST | `/users/{user_id}/force-password-reset` | 20/hr per IP | Send password reset email to user |
| POST | `/users/invite` | 20/hr per IP | Invite a user by email (sends invite link) |

## Environment Variables

See `.env.example` for a complete template.


## RBAC

Users have a `role` field (`user` by default, `admin` available). The role is:
- Embedded in JWT claims at login — allows fast local checks
- Returned by `GET /api/auth/validate-token` — authoritative live lookup for consumer services

When a role changes, `role_changed_at` is set and all existing tokens for that user are invalidated (same pattern as password changes).

**Bootstrap the first admin:**
```bash
python -m scripts.promote_admin admin@example.com
# Or inside Docker:
docker compose exec auth-service python -m scripts.promote_admin admin@example.com
```


## Testing

Tests use a real PostgreSQL database with per-test transaction rollback. Redis is mocked via `fakeredis`.

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```
