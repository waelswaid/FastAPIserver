# Architecture Diagrams

## 1. System Context

High-level view of the auth-system and its external dependencies.

```mermaid
graph TB
    Client["Client
    (Browser / Mobile / Service)"]

    subgraph auth-system ["Auth System"]
        App["FastAPI Application
        :8000"]
    end

    PG[("PostgreSQL
    Users, Tokens, Actions")]
    Redis[("Redis
    Rate Limiting")]
    Mailgun["Mailgun API
    Transactional Email"]

    Client -- "HTTP/REST" --> App
    App -- "SQLAlchemy" --> PG
    App -- "aioredis" --> Redis
    App -- "HTTP POST" --> Mailgun
    Mailgun -. "Email" .-> Client
```

## 2. Docker Deployment

Container orchestration as defined in `docker-compose.example.yml`.

```mermaid
graph LR
    subgraph Docker Compose
        subgraph app ["app container"]
            Entrypoint["entrypoint.sh
            alembic upgrade head
            uvicorn :8000"]
        end

        subgraph pg ["postgres:16-alpine"]
            PG[("PostgreSQL
            :5432")]
        end

        subgraph rd ["redis:7-alpine"]
            Redis[("Redis
            :6379")]
        end
    end

    Host["Host :8000"] --> Entrypoint
    Entrypoint -- "depends_on: healthy" --> PG
    Entrypoint -- "depends_on: healthy" --> Redis

    Volume[("pgdata volume")] -.- PG
```

## 3. Application Layer Architecture

The service layer pattern: routes → services → repositories → database.

```mermaid
graph TB
    subgraph API ["API Layer (app/api)"]
        direction LR
        AuthRoutes["auth_routes.py
        /api/auth/*"]
        UserRoutes["user_routes.py
        /api/users/*"]
        AdminRoutes["admin_routes.py
        /api/admin/*"]
        HealthRoutes["health_routes.py
        /health"]
    end

    subgraph Deps ["Dependencies (app/api/dependencies)"]
        direction LR
        AuthDep["auth_dependency.py
        get_current_user
        require_role"]
        RateLimiter["rate_limiter.py
        RateLimiter class"]
    end

    subgraph Services ["Service Layer (app/services)"]
        direction LR
        AuthSvc["auth_services.py
        login, logout, refresh,
        reset, verify, change pwd"]
        UserSvc["user_services.py
        registration,
        profile update"]
        AdminSvc["admin_services.py
        role management"]
    end

    subgraph Repos ["Repository Layer (app/repositories)"]
        direction LR
        UserRepo["user_repository.py"]
        PendingRepo["pending_action_repository.py"]
        BlacklistRepo["token_blacklist_repository.py"]
    end

    subgraph Models ["Models (app/models)"]
        direction LR
        User["User"]
        PendingAction["PendingAction"]
        TokenBlacklist["TokenBlacklist"]
    end

    DB[("PostgreSQL")]

    API --> Deps
    API --> Services
    Services --> Repos
    Repos --> Models
    Models --> DB
    AuthDep --> BlacklistRepo
    AuthDep --> UserRepo
    RateLimiter --> Redis[("Redis")]
```

## 4. Middleware Pipeline

Order of middleware processing for every incoming request.

```mermaid
graph LR
    Request["Incoming
    Request"] --> CORS

    subgraph Middleware Stack
        CORS["CORS
        Middleware"] --> Logging["Request Logging
        Middleware
        (+ correlation ID)"] --> RateLimit["Rate Limit
        Headers
        Middleware"]
    end

    RateLimit --> Router["FastAPI
    Router"]

    Router --> RateLimiterDep["Rate Limiter
    (dependency)"]
    Router --> AuthDep["Auth
    (dependency)"]
    Router --> Handler["Route
    Handler"]

    Handler --> Response["Response
    + X-Request-ID
    + X-RateLimit-*"]
```

## 5. Database Schema

Entity-relationship diagram for all three models.

```mermaid
erDiagram
    users {
        UUID id PK
        String first_name
        String last_name
        String email UK
        String password_hash
        Boolean is_verified
        String role
        DateTime created_at
        DateTime password_changed_at
        DateTime role_changed_at
    }

    pending_actions {
        UUID id PK
        UUID user_id FK
        String action_type
        String code
        DateTime expires_at
        DateTime created_at
    }

    token_blacklist {
        String jti PK
        DateTime expires_at
    }

    users ||--o{ pending_actions : "has"
    users ||--o{ token_blacklist : "revoked tokens"
```

## 6. Authentication & Token Flow

Login, token refresh, and logout sequence.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant S as AuthService
    participant R as Repositories
    participant DB as PostgreSQL

    Note over C,DB: Login
    C->>A: POST /api/auth/login {email, password}
    A->>S: user_login()
    S->>R: find_user_by_email()
    R->>DB: SELECT ... WHERE email = ?
    DB-->>R: User row
    R-->>S: User
    S->>S: verify_password(input, hash)
    S->>S: check is_verified
    S->>S: create_access_token + create_refresh_token
    S-->>A: {access_token, refresh_token}
    A-->>C: 200 + access_token body + refresh_token cookie

    Note over C,DB: Authenticated Request
    C->>A: GET /api/users/me [Bearer token]
    A->>A: decode JWT, check blacklist
    A->>R: find_user_by_id()
    R->>DB: SELECT
    DB-->>R: User
    A-->>C: 200 UserRead

    Note over C,DB: Token Refresh
    C->>A: POST /api/auth/refresh [cookie]
    A->>S: refresh_access_token()
    S->>S: decode refresh token
    S->>R: is_blacklisted(jti)
    S->>S: create new access_token
    S-->>A: new access_token
    A-->>C: 200 + new access_token

    Note over C,DB: Logout
    C->>A: POST /api/auth/logout [Bearer + cookie]
    A->>S: logout()
    S->>R: add_to_blacklist(access_jti)
    S->>R: add_to_blacklist(refresh_jti)
    R->>DB: INSERT into token_blacklist
    A-->>C: 204 + clear cookie
```

## 7. Password Reset Flow

Forgot password → validate code → reset password.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant S as AuthService
    participant R as Repositories
    participant DB as PostgreSQL
    participant M as Mailgun

    Note over C,M: Request Reset
    C->>A: POST /api/auth/forgot-password {email}
    A->>S: request_password_reset()
    S->>R: find_user_by_email()
    R->>DB: SELECT
    DB-->>R: User (or null)
    S->>S: generate code + expiry
    S->>R: upsert_action(password_reset_code)
    R->>DB: INSERT/UPDATE pending_actions
    S->>M: send_password_reset_email(email, code)
    M-.->C: Email with reset link (?code=...)
    S-->>A: (always succeeds — no email leak)
    A-->>C: 200 "If account exists, email sent"

    Note over C,M: Validate Code (optional preflight)
    C->>A: GET /api/auth/reset-password?code=abc123
    A->>S: validate_reset_code()
    S->>R: find_user_by_action_code_for_update()
    R->>DB: SELECT ... FOR UPDATE
    DB-->>R: User + Action
    S->>S: check expiry
    S-->>A: valid / invalid
    A-->>C: 200 {valid: true}

    Note over C,M: Reset Password
    C->>A: POST /api/auth/reset-password {code, new_password}
    A->>S: reset_password_via_code()
    S->>R: find_user_by_action_code_for_update()
    R->>DB: SELECT ... FOR UPDATE
    S->>S: check expiry
    S->>R: update_password(new_hash)
    S->>R: delete_action()
    S->>R: delete_actions(password_reset_*)
    R->>DB: UPDATE + DELETE
    S-->>A: success
    A-->>C: 200 "Password reset successfully"
```

## 8. Email Verification Flow

Registration → verify via code or token.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant S as Services
    participant R as Repositories
    participant DB as PostgreSQL
    participant M as Mailgun

    Note over C,M: Registration
    C->>A: POST /api/users/create {name, email, password}
    A->>S: user_create()
    S->>R: create_user()
    R->>DB: INSERT (is_verified=false)
    S->>S: generate verification code + expiry
    S->>R: upsert_action(email_verification_code)
    R->>DB: INSERT pending_actions
    S->>M: send_verification_email(email, code)
    M-.->C: Email with verify link (?code=...)
    A-->>C: 201 UserRead

    Note over C,M: Verify via Code (from email link)
    C->>A: GET /api/auth/verify-email?code=abc123
    A->>S: verify_email_code()
    S->>R: find_user_by_action_code_for_update()
    R->>DB: SELECT ... FOR UPDATE
    S->>S: check expiry
    S->>R: verify_user(user)
    R->>DB: UPDATE is_verified=true
    S->>R: delete_actions(email_verification_*)
    R->>DB: DELETE
    A-->>C: 200 "Email verified"
```

## 9. Rate Limiting Architecture

Redis sliding window implementation.

```mermaid
graph TB
    Request["Incoming Request"] --> Dep["RateLimiter
    Dependency"]

    Dep --> BuildKey["Build Key
    {prefix}:{ip}:{email}"]
    BuildKey --> Lua["Redis Lua Script
    (atomic)"]

    subgraph Redis ["Redis Sliding Window"]
        Lua --> Window["ZSET per key
        score = timestamp
        member = request_id"]
        Lua --> Cleanup["Remove entries
        older than window"]
        Lua --> Count["Weighted count:
        prev_window × overlap +
        current_window"]
    end

    Lua --> Decision{allowed?}
    Decision -- "Yes" --> Handler["Route Handler"]
    Decision -- "No" --> Reject["429 Too Many Requests"]

    Handler --> MW["Rate Limit Headers MW"]
    MW --> Response["Response
    X-RateLimit-Limit
    X-RateLimit-Remaining
    X-RateLimit-Reset"]

    Lua -. "Redis down" .-> Fallback["Fail Open
    (allow request)"]
    Fallback --> Handler
```

## 10. Auth Dependency & RBAC

How `get_current_user` and `require_role` validate every authenticated request.

```mermaid
flowchart TB
    Request["Request with
    Bearer token"] --> Extract["Extract token
    from Authorization header"]

    Extract --> Decode["Decode JWT
    (verify signature + expiry)"]
    Decode -- "invalid/expired" --> R401a["401 Unauthorized"]

    Decode -- "valid" --> Blacklist{"Token JTI
    blacklisted?"}
    Blacklist -- "yes" --> R401b["401 Unauthorized
    (revoked)"]

    Blacklist -- "no" --> FetchUser["Fetch user
    by token sub (user_id)"]
    FetchUser -- "not found" --> R401c["401 Unauthorized"]

    FetchUser -- "found" --> PwdCheck{"Token issued
    before password_changed_at?"}
    PwdCheck -- "yes" --> R401d["401 Unauthorized
    (stale token)"]

    PwdCheck -- "no" --> RoleCheck{"Token issued
    before role_changed_at?"}
    RoleCheck -- "yes" --> R401e["401 Unauthorized
    (stale token)"]

    RoleCheck -- "no" --> RBAC{"require_role
    specified?"}
    RBAC -- "no" --> Allow["Return User
    to route handler"]
    RBAC -- "yes" --> RoleMatch{"User role in
    allowed_roles?"}
    RoleMatch -- "no" --> R403["403 Forbidden"]
    RoleMatch -- "yes" --> Allow
```
