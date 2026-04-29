  Critical (correctness / security risk)                                                                                                 
                                                                                                                                         
  C1 — Token blacklist fails open on Redis outage. app/repositories/token_blacklist_repository.py:13–26. If Redis is down, blacklisted   
  tokens (logout, password-reset reuse, role change) become valid again. Same fail-open pattern in rate limiter and account lockout.     
  Already documented in SECURITY_ISSUES.txt.                                                                                             
                                                                                                                                         
  C2 — Race condition in upsert_action. app/repositories/pending_action_repository.py:18–34. with_for_update() locks zero rows when the  
  row doesn't exist; concurrent requests can double-insert before the unique constraint catches them.                                    
                                                                                                                                         
  C3 — Ephemeral state on the users table. is_verified, password_changed_at, role_changed_at (app/models/user.py:24,34,45). CLAUDE.md    
  explicitly forbids this — they belong in pending_actions or a dedicated audit/state table.                                             
                                                                                                                                         
  C4 — Synchronous email + sync Argon2 inside async event loop. app/utils/email.py uses blocking requests.post; password_hash.verify runs
   on the event loop. Under concurrent load, both become DoS vectors. Already in SECURITY_ISSUES.txt.

  C5 — settings = Settings() at module import. app/core/config.py:11. Mutable singleton, no validation that RSA keys are well-formed,
  dangerous localhost defaults for APP_BASE_URL and REDIS_URL in prod.

  C6 — Domain exception layer barely exists. app/exceptions.py has only DuplicateEmailError. CLAUDE.md mandates repos catch
  IntegrityError and raise domain exceptions; meanwhile services raise generic ValueError (app/utils/tokens.py:100,116,132,147) and
  routes catch broadly.

  ---
  Major (architecture / layering violations)

  M1 — auth_services.py (356 lines) tangles four concerns: login/refresh/logout, password-reset (JWT + code), email-verification (JWT +
  code), invite. Helper _get_valid_invite and parallel JWT-vs-code flows duplicate logic. Splitting candidates:
  password_reset_service.py, email_verification_service.py, invite_service.py.

  M2 — Layering violations in routes.
  - app/api/routes/user_routes.py:8,44,46 calls a repo function directly and runs db.refresh(current_user) from the route.
  - app/api/routes/health_routes.py:23–39 runs db.execute(text("SELECT 1")) from the route.

  M3 — Layering violations in services (raw SQLAlchemy / direct mutation).
  - app/services/oauth_service.py:97 raw db.query(User).filter(...).
  - app/services/oauth_service.py:114–115 and app/services/admin_services.py:48 mutate ORM attributes directly + db.commit() instead of
  going through repos.

  M4 — Magic password-hash sentinels ("!oauth", "!invited") scattered across auth_services.py:147,306, admin_services.py:70,
  oauth_service.py:126, user_services.py:35. Should be enum/constants.

  M5 — Missing IntegrityError handling in oauth_account_repository.create_oauth_account (lines 22–40). Inconsistent with
  user_repository.py:20–24.

  M6 — Inconsistent FOR UPDATE locking before mutation.
  - admin_services.disable_user reads with lock then calls update_user_disabled_status which may not preserve it; also assigns
  password_changed_at directly outside repo.
  - admin_services.change_user_role (line 15) uses find_user_by_id (no lock) before update_user_role.
  - Repo update functions like update_password, verify_user, update_user_role accept any User instance — no enforcement that caller used
  find_user_by_id_for_update.

  M7 — Duplicated token-pair / blacklist-and-upsert boilerplate. auth_services.logout and user_services.delete_own_account both
  decode-and-blacklist; auth_services.request_password_reset and admin_services.force_password_reset both upsert two pending actions plus
   a JTI in identical 8-line patterns.

  M8 — tokens.py (147 lines) tangles signing, verification, and token-type-specific logic with no caching of parsed RSA keys; raises bare
   ValueError.

  M9 — email.py repeats Mailgun client setup three times with inline f-string templates and no abstraction; not testable without
  monkeypatching requests.

  M10 — rate_limiter.py (313 lines) holds two concerns. RateLimiter class + AccountLockout class + 80+ lines of ASCII-diagram comments +
  10 module-level RateLimiter() instances with hardcoded config lookups.

  M11 — No refresh-token rotation / family. A stolen refresh token is silently usable for its full TTL. From SECURITY_ISSUES.txt.

  M12 — enums.py is 6 lines. Audit event names, action types (ACTION_PASSWORD_RESET_JTI, ACTION_INVITE, etc.), cookie names
  (refresh_token, oauth_state), and status strings are scattered as magic strings across services and routes.

  M13 — Test fixture sprawl. _login, _auth_header, _make_admin, _extract_invite_code are redefined across 8 test files.
  test_admin_management.py is 537 lines and bundles three independent admin features. fake_redis autouse without per-test cleanup risks
  state bleed.

  M14 — CI gaps. No type checking, no alembic check for head divergence, no security scanner. flake8 --exit-zero makes complexity
  warnings non-fatal.

  M15 — entrypoint.sh runs alembic upgrade head without retry/error handling; no DB readiness probe when image runs outside compose.

  ---
  Minor (consistency / quality)

  - Inconsistent commit: bool parameter on repo update functions (update_user_role, update_user_profile hard-commit; others don't).
  - Unused logger in auth_routes.py, missing audit log on /logout (line 87–90).
  - Mixed sync/async on similar endpoints in auth_routes.py with no clear boundary.
  - /users/create is non-RESTful (verb in URL).
  - Cookie names + 600-second OAuth state TTL hardcoded in auth_routes.py 5–9 times.
  - Literal["user", "admin"] in admin_schema.py:6 instead of referencing UserRole enum.
  - Repeated Field(min_length=8, max_length=128) for password across 4 schema files.
  - String columns without length on first_name, last_name (indexed).
  - Missing index=True on pending_actions.user_id; missing index on expires_at.
  - Empty Alembic downgrade in initial migration.
  - requirements.txt mixes prod and dev (Streamlit, pytest, fakeredis); >= ranges on cryptography/redis.
  - .env.example has \n-escaped RSA key examples and cryptic placeholders.
  - notes.py at repo root looks like personal study notes — should probably be moved or deleted.
  - SECURITY_ISSUES.txt itself should become tracked issues or a docs/ file.

  ---
  Themes / natural refactor slices

  Most of these findings cluster into 8 coherent slices that you could tackle one at a time:

  1. Domain exceptions + repository hardening — build out exceptions.py, push IntegrityError catching to all repos, replace ValueError in [Done]
   tokens.py with domain types. Unblocks cleaner service layer. (C6, M5, M8 partial)
  2. Split auth_services.py into focused modules; extract shared helpers (token-pair creation, blacklist-jti, upsert-pending-action). [Done]
  (M1, M7)
  3. Move ephemeral state off users — verification, password/role audit timestamps to pending_actions or a new user_audit table.
  Migration involved. (C3)
  4. Fix Redis fail-open posture — fail-closed for blacklist; circuit-breaker / explicit degraded mode for rate limit. (C1)
  5. Async-correctness pass — httpx.AsyncClient for Mailgun, asyncio.to_thread for Argon2, audit sync/async boundaries in services. (C4,
  M9)
  6. Config + enums + constants pass — frozen settings, RSA key validation, fill out enums, kill magic strings ("!oauth", action types,
  cookie names). (C5, M4, M12)
  7. Layering audit + repo enforcement — fix the route/service layering violations, standardize commit: bool, ensure every mutation goes
  through a locked-read repo function. (M2, M3, M6, minor consistency items)
  8. Test/CI/Ops hygiene — promote duplicated helpers to fixtures, split test_admin_management.py, add type-check + alembic-check +
  bandit to CI, harden entrypoint. (M13, M14, M15)
