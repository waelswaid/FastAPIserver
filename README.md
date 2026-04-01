# FastAPI Auth System

A production-ready authentication API built with FastAPI. Provides user registration, email verification, JWT-based authentication, password reset, Google OAuth, admin management, and Redis-backed rate limiting out of the box.

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
git clone https://github.com/YOUR_USERNAME/auth-system.git
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

## API Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check (database + Redis status) |

### Users (`/api`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| POST | `/users/create` | No | 5/hr per IP | Register a new user |
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
| GET | `/google` | No | 40/hr per IP | Redirects to Google consent screen |
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

See `.env.example` for a complete template. Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_PRIVATE_KEY` | RSA private key for signing tokens |
| `JWT_PUBLIC_KEY` | RSA public key for verifying tokens |
| `JWT_ALGORITHM` | Signing algorithm (default: `RS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL (default: `30`) |
| `MAILGUN_API_KEY` | Mailgun API key |
| `MAILGUN_DOMAIN` | Mailgun sending domain |
| `MAILGUN_FROM_EMAIL` | From address for emails |
| `APP_BASE_URL` | Base URL for email links |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Reset code TTL (default: `15`) |
| `EMAIL_VERIFICATION_EXPIRE_MINUTES` | Verification code TTL (default: `1440`) |
| `REDIS_URL` | Redis connection string |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL |
| `INVITE_URL` | Frontend URL for invite links |
| `INVITE_EXPIRE_MINUTES` | Invite code TTL (default: `4320` / 3 days) |
| `MAX_ATTEMPTS_UNTILL_LOCKOUT` | Failed logins before lockout (default: `10`) |
| `LOCKOUT_TIME_SECONDS` | Lockout duration (default: `900` / 15 min) |

## Architecture Diagrams

See [Architecture Diagrams](docs/architecture-diagrams.md) for detailed Mermaid diagrams covering:

1. **System Context** — auth-system and its external dependencies
2. **Docker Deployment** — container orchestration
3. **Application Layer Architecture** — service layer pattern (routes → services → repos → DB)
4. **Middleware Pipeline** — CORS → logging → rate limit headers → routing
5. **Database Schema** — ER diagram (users, pending_actions, oauth_accounts)
6. **Authentication & Token Flow** — login, authenticated requests, refresh, logout
7. **Password Reset Flow** — forgot → validate code → reset
8. **Email Verification Flow** — registration → verify via code
9. **Rate Limiting Architecture** — Redis sliding window
10. **Auth Dependency & RBAC** — token validation and role checking

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

## Documentation

- [Architecture Diagrams](docs/architecture-diagrams.md) — system diagrams in Mermaid
- [Microservice Architecture](docs/microservice-architecture.md) — how auth-system integrates with other services
- [Rate Limiting](docs/redis-rate-limiting.md) — how the Redis sliding window counter works
- [Docker Guide](docs/docker-guide.md) — Docker setup instructions
- [CORS & Nginx](docs/cors_and_nginx.md) — CORS and reverse proxy configuration

## Contributing

Contributions are welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest tests/ -v`)
5. Open a pull request
