# Auth System Roadmap

Features needed to make this a fully reliable authentication and authorization system.

---

## 1. Auth Flows

- [ ] **Refresh token endpoint** — `POST /api/auth/refresh`: accepts a refresh token, returns a new access token. Logic exists in `JWTUtility` but no route is wired up.
- [ ] **Logout / token revocation** — maintain a server-side blacklist (e.g. Redis or DB table) of invalidated tokens so stolen tokens can be revoked before expiry.
- [ ] **Password reset** — `POST /api/auth/forgot-password` sends a reset link; `POST /api/auth/reset-password` validates a short-lived signed token and updates the password hash.
- [ ] **Email verification** — send a verification link on signup; block login until the email is confirmed.

---

## 2. User Management

- [ ] **Update profile** — `PATCH /api/users/me`: allow users to update their name and/or email (email change should re-trigger verification).
- [ ] **Change password** — `POST /api/users/me/change-password`: requires the current password before accepting the new one.
- [ ] **Delete account** — `DELETE /api/users/me`: soft-delete or hard-delete the authenticated user's account.

---

## 3. Authorization

- [ ] **Role-based access control (RBAC)** — add a `role` field to the `User` model (e.g. `user`, `admin`). Add a `require_role()` dependency to restrict sensitive endpoints to admins.
- [ ] **Admin endpoints** — `GET /api/admin/users` (list all users), `DELETE /api/admin/users/{id}`, `PATCH /api/admin/users/{id}/role`.

---

## 4. Security Hardening

- [ ] **Rate limiting on login** — limit failed login attempts per IP/email to prevent brute-force attacks.
- [ ] **Secure refresh token storage** — refresh tokens should be stored as HTTP-only cookies, not returned in the JSON body.
- [ ] **HTTPS enforcement** — ensure the app rejects plain HTTP in production.
- [ ] **CORS configuration** — restrict allowed origins via FastAPI's `CORSMiddleware`.
- [ ] **Password strength validation** — enforce complexity rules beyond just min/max length.
- [ ] **Token type enforcement** — current `decode_access_token` already checks token type; ensure refresh tokens cannot be used as access tokens anywhere.
- [ ] **Production cookie flag** — `secure` on the refresh token cookie in `auth_routes.py` is currently driven by `ENVIRONMENT == "production"`. Ensure `ENVIRONMENT=production` is set in the production `.env` file so the cookie is HTTPS-only in prod.

---

## 5. Code Quality / Architecture Fixes

- [ ] **Move `HTTPException` out of `user_repository.py`** — `create_user` currently raises an HTTP-level exception from the repo layer. It should raise a domain exception (e.g. `DuplicateEmailError`) and let the service or route layer translate it.
- [ ] **Database migrations with Alembic** — replace `Base.metadata.create_all()` (if used) with proper migration scripts so schema changes are tracked and reversible.
- [ ] **Consistent SQLAlchemy style** — `user_repository.py` uses legacy `db.query()` style. Migrate to the SQLAlchemy 2.0 `select()` style to match the `User` model's `Mapped`/`mapped_column` declarations.

---

## 6. Testing

- [ ] **Unit tests for `JWTUtility`** — test token creation, expiry, wrong type rejection, tampered signatures.
- [ ] **Unit tests for `auth_services.py`** — test login with valid credentials, wrong password, non-existent user.
- [ ] **Integration tests** — test full request/response cycle for `/login`, `/me`, `/refresh` using a test database.
- [ ] **Test coverage enforcement** — add a coverage threshold to CI so it fails below an acceptable level.

---

## 7. Observability

- [ ] **Structured logging** — log auth events (login success/failure, token refresh, password reset) with user ID and timestamp for auditing.
- [ ] **Health check endpoint** — `GET /api/health` returns app and DB status (used by load balancers and monitoring tools).
- [ ] **Error tracking** — integrate with a service like Sentry to capture unhandled exceptions in production.

---

## 8. Configuration & Deployment

- [ ] **Environment validation on startup** — fail fast if required env vars (`JWT_SECRET_KEY`, `DATABASE_URL`) are missing or obviously weak.
- [ ] **Secret rotation support** — design token verification to support multiple valid signing keys during rotation periods.
- [ ] **Dockerfile + docker-compose** — containerize the app and database for consistent local and production environments.
