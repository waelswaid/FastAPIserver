# FastAPI Auth System

A production-ready authentication API built with FastAPI. Provides user registration, email verification, JWT-based authentication, password reset, and Redis-backed rate limiting out of the box.

Use it as a standalone auth backend or as the foundation for your own application.

## Features

- **JWT authentication** — access tokens (30 min) + refresh tokens (httponly cookie, 1 day)
- **RBAC** — role-based access control (user/admin), role embedded in JWT and validate-token
- **Email verification** — code-based and token-based flows via Mailgun
- **Password reset** — secure reset flow with expiring codes
- **Change password** — authenticated password change with token invalidation
- **Profile update** — update first_name/last_name via PATCH /users/me
- **Admin endpoints** — role management + user listing (admin-only)
- **Rate limiting** — Redis sliding window counter (Lua script), per-IP and per-email
- **Token revocation** — blacklist table + password/role-change invalidation
- **Argon2id** password hashing
- **Row-level locks** on verification and reset to prevent race conditions

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.135 + Uvicorn |
| Database | PostgreSQL + SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | PyJWT (HS256) |
| Hashing | Argon2id (pwdlib) |
| Email | Mailgun API |
| Rate Limiting | Redis 7 (sliding window) |
| Testing | pytest + httpx + fakeredis |

## Quickstart

### Option 1: Docker (recommended)

```bash
cp docker-compose.example.yml docker-compose.yml
cp .env.example .env
# Edit .env with your secrets (JWT key, Mailgun credentials, etc.)
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

## API Endpoints

### Users (`/api`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| POST | `/users/create` | No | 5/hr per IP | Register a new user |
| GET | `/users/me` | Bearer | No | Get authenticated user profile |
| PATCH | `/users/me` | Bearer | No | Update profile (first_name, last_name) |

### Auth (`/api/auth`)

| Method | Path | Auth | Rate Limited | Description |
|--------|------|------|--------------|-------------|
| POST | `/login` | No | 10/hr per IP+email, 30/hr per IP | Login, returns access + refresh tokens |
| POST | `/refresh` | Cookie | 30/hr per IP | Refresh access token |
| POST | `/logout` | Bearer | No | Revoke tokens and clear cookie |
| POST | `/change-password` | Bearer | 5/hr per IP | Change password (requires current password) |
| POST | `/forgot-password` | No | 5/hr per IP+email | Send password reset email |
| GET | `/reset-password` | No | 10/hr per IP | Validate reset code from email |
| POST | `/reset-password` | No | 10/hr per IP | Reset password with code or token |
| POST | `/resend-verification` | No | 5/hr per IP+email | Resend verification email |
| GET | `/verify-email` | No | 10/hr per IP | Verify email via code from email link |
| POST | `/verify-email` | No | No | Verify email via JWT token |
| GET | `/validate-token` | Bearer | No | Validate token and return user info (service-to-service) |

### Admin (`/api/admin`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/` | Admin | List users (optional `?role=` filter, pagination) |
| PATCH | `/users/{user_id}/role` | Admin | Change a user's role (`user` or `admin`) |

## Architecture Diagrams

See [Architecture Diagrams](docs/architecture-diagrams.md) for detailed Mermaid diagrams covering:

1. **System Context** — auth-system and its external dependencies
2. **Docker Deployment** — container orchestration
3. **Application Layer Architecture** — service layer pattern (routes → services → repos → DB)
4. **Middleware Pipeline** — CORS → logging → rate limit headers → routing
5. **Database Schema** — ER diagram (users, pending_actions, token_blacklist)
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

- [Microservice Architecture](docs/microservice-architecture.md) — how auth-system and nutrifit work together
- [Rate Limiting](docs/redis-rate-limiting.md) — how the Redis sliding window counter works

## Contributing

Contributions are welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest tests/ -v`)
5. Open a pull request
