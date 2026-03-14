# Phase 1 — JWT Auth Implementation Checklist for Your FastAPI Project

This checklist is designed for your **current layered architecture**:

- `routes -> services -> repositories -> models/database`
- existing `User` model
- existing registration flow
- existing password hashing utility
- existing DB session dependency

The goal of this phase is to add:

- login with email + password
- JWT access token generation
- token validation
- current authenticated user extraction
- protected endpoints

---

# Phase 1 Goal

By the end of this phase, your backend should support this flow:

1. user registers
2. user logs in with email + password
3. server returns JWT access token
4. client sends token in `Authorization: Bearer <token>`
5. server validates token
6. server loads current user from DB
7. protected endpoints work only for authenticated users


---

# Step 1 — Define What Auth Needs to Add

Before touching files, be clear about the missing pieces.

## New capabilities you need

- [X] login request schema (not verified yet)
- [X] token response schema (not yet verified)
- [X] repository method to find user by email
- [X] repository method to find user by id
- [X] JWT utility for token creation and decoding
- [ ] auth service for login logic
- [ ] auth route for login endpoint
- [ ] dependency that extracts current user from bearer token
- [ ] one protected test endpoint
- [ ] protection added to selected real endpoints
app/schemas/login_request.py
app/schemas/token_response.py


---

# Step 2 — Extend Configuration for JWT

You already have config for DB settings. Now extend config for auth settings.

## Decide your JWT settings

- [ ] choose a secret key
- [ ] choose an algorithm
- [ ] choose access token expiration duration

## Add these to your config layer conceptually

Your settings should now include something like:

- [ ] `JWT_SECRET_KEY`
- [ ] `JWT_ALGORITHM`
- [ ] `ACCESS_TOKEN_EXPIRE_MINUTES`

## Add them to `.env`

- [ ] add a secret key entry
- [ ] add algorithm entry
- [ ] add expiration entry

## Verify

- [ ] your app can still start after config changes
- [ ] settings are loaded correctly
- [ ] you are not hardcoding secrets in random files

## Important notes

- [ ] secret must come from config/environment
- [ ] expiration should be configurable
- [ ] algorithm should be centralized in config

---

# Step 3 — Add User Lookup Methods in Repository

Login cannot work unless you can fetch users from DB by email and later by id.

## In `user_repository.py`, conceptually add:

### A method to get user by email
Purpose:
- [ ] receive email
- [ ] query `users` table
- [ ] return matching user or `None`

### A method to get user by id
Purpose:
- [ ] receive user id
- [ ] query `users` table
- [ ] return matching user or `None`

## Verify after adding repository methods

- [ ] repository still only does DB access
- [ ] repository does not know about JWT
- [ ] repository does not know about HTTP requests
- [ ] repository does not verify passwords
- [ ] repository returns ORM user objects or `None`

## Self-check

- [ ] "get by email" is for login
- [ ] "get by id" is for current authenticated user

---

# Step 4 — Create Auth Schemas

Do not reuse registration schemas for login. Authentication is a separate concern.

## Create a dedicated auth schema file

Suggested concept:
- [ ] `auth_schema.py`

## Add a login request schema

Fields should include:

- [ ] email
- [ ] password

Do **not** include:

- [ ] name
- [ ] created_at
- [ ] password_hash
- [ ] id

## Add a token response schema

Fields should include at least:

- [ ] `access_token`
- [ ] `token_type`

Optional later:
- [ ] user info
- [ ] expiration info

But keep Phase 1 minimal.

## Verify

- [ ] login request schema is only for login input
- [ ] token response schema is only for login output
- [ ] auth schemas are not mixed into user registration schemas

---

# Step 5 — Design the JWT Payload

Before creating the JWT utility, decide what the token will contain.

## Decide what identity claim the token should carry

Recommended:
- [ ] user id

Alternative:
- [ ] email

Use one stable identity field consistently.

## Decide token expiration behavior

- [ ] token should expire after a fixed duration
- [ ] expiration should be added inside token claims
- [ ] expiration should use your configured minutes value

## Decide the minimum token contents

Your token should conceptually contain:

- [ ] user identity claim
- [ ] expiration claim

Avoid adding unnecessary data for Phase 1.

## Verify

- [ ] token identifies the user clearly
- [ ] token does not store sensitive data like plaintext password
- [ ] token data is minimal and purposeful

---

# Step 6 — Create the JWT Utility Module

Now build a utility whose only job is token mechanics.

## Create a new file

Suggested concept:
- [ ] `app/utils/security/jwt_handler.py`

## This utility should conceptually provide:

### Token creation function
Responsibilities:
- [ ] receive user identity data
- [ ] attach expiration
- [ ] sign token using secret + algorithm
- [ ] return token string

### Token decode/validate function
Responsibilities:
- [ ] receive token string
- [ ] decode token using secret + algorithm
- [ ] validate signature
- [ ] validate expiration
- [ ] return decoded payload or fail

## This utility should **not** do these things

- [ ] do not query the DB
- [ ] do not read request headers directly
- [ ] do not know anything about FastAPI routes
- [ ] do not decide business rules like login success

## Verify

- [ ] JWT utility is reusable
- [ ] JWT utility depends on config, not hardcoded values
- [ ] JWT utility is focused only on token creation/decoding

---

# Step 7 — Create the Auth Service

This service will contain the business logic for login.

## Create a new service file

Suggested concept:
- [ ] `app/services/auth_services.py`

## Add a login/authenticate flow

The auth service should perform these steps in order:

1. [ ] receive login credentials
2. [ ] use repository to fetch user by email
3. [ ] if no user exists, reject login
4. [ ] compare submitted password against stored password hash
5. [ ] if password is wrong, reject login
6. [ ] if password is correct, create JWT
7. [ ] return token response object

## Important boundaries

The auth service **should**:
- [ ] use repository for user lookup
- [ ] use password utility for password verification
- [ ] use JWT utility for token generation
- [ ] raise or return proper failure when login is invalid

The auth service **should not**:
- [ ] directly parse HTTP headers
- [ ] directly manage route definitions
- [ ] directly perform raw SQL

## Verify

- [ ] login logic is centralized in one service
- [ ] password verification uses existing hash utility
- [ ] service returns token response, not raw DB data
- [ ] incorrect credentials are handled cleanly

---

# Step 8 — Create Auth Routes

Now expose authentication through dedicated routes.

## Create a new route file

Suggested concept:
- [ ] `app/api/routes/auth_routes.py`

## Add a login endpoint

This route should conceptually:

- [ ] accept login request body
- [ ] receive DB session using dependency injection
- [ ] call auth service
- [ ] return token response

## Keep the route thin

The route should **not**:
- [ ] query users directly
- [ ] compare passwords directly
- [ ] create token manually
- [ ] contain business logic

It should only:
- [ ] receive request
- [ ] call service
- [ ] return response

## Register the new router in `main.py`

- [ ] import auth router
- [ ] include it in the FastAPI app

## Verify

- [ ] app starts after adding auth router
- [ ] login endpoint appears in Swagger
- [ ] login route is reachable

---

# Step 9 — Test Login Before Protected Routes

Do not move on until login works.

## Test sequence

### Test A — register a user
- [ ] create a test user through your registration route

### Test B — login with correct credentials
- [ ] send correct email/password
- [ ] confirm response is success
- [ ] confirm token is returned

### Test C — login with wrong password
- [ ] confirm login fails

### Test D — login with non-existent email
- [ ] confirm login fails

## Verify

- [ ] token is returned only when credentials are valid
- [ ] wrong credentials do not expose whether password or email was specifically wrong unless you intentionally design it that way
- [ ] registration + login both work independently

---

# Step 10 — Add Current User Dependency

Login alone is not enough. Protected routes need a reusable authentication dependency.

## Create a dependency concept

Suggested location:
- [ ] auth dependency module
- [ ] or keep temporarily in auth service layer if you prefer, but a separate dependency file is cleaner

## This dependency should perform these steps

1. [ ] read `Authorization` header
2. [ ] verify it is a bearer token
3. [ ] extract token string
4. [ ] decode token using JWT utility
5. [ ] extract user identity from token payload
6. [ ] fetch user from DB using repository
7. [ ] return authenticated user object

## This dependency should fail if:

- [ ] no authorization header exists
- [ ] header format is wrong
- [ ] token is invalid
- [ ] token is expired
- [ ] token payload is missing user identity
- [ ] user no longer exists in DB

## Verify

- [ ] dependency returns a real `User` object when token is valid
- [ ] dependency blocks access when token is missing or invalid
- [ ] dependency does not contain unrelated business logic

---

# Step 11 — Create a Protected Test Endpoint

Before securing your real task routes, create a simple test endpoint.

## Add one protected route

Purpose:
- [ ] verify the current-user dependency works end-to-end

This route should conceptually:
- [ ] require current authenticated user
- [ ] return simple success info
- [ ] optionally return authenticated user identity

## Why this matters

It lets you isolate auth testing from the rest of your app.

If this endpoint works, then all of these are working:

- [ ] bearer header extraction
- [ ] token decode
- [ ] token validation
- [ ] user lookup by token identity
- [ ] protected access control

## Verify

### Request without token
- [ ] should fail

### Request with bad token
- [ ] should fail

### Request with valid token
- [ ] should succeed

Do not continue until this is fully working.

---

# Step 12 — Protect Real Endpoints

Once the protected test endpoint works, start protecting actual feature routes.

## Decide which routes stay public

Usually these remain public:
- [ ] register
- [ ] login

## Decide which routes become protected

For your current project, likely:
- [ ] list tasks
- [ ] create task
- [ ] complete task

## Apply the current-user dependency to these routes

Each protected route should now require authentication before business logic runs.

## Verify

### Without token
- [ ] protected task routes fail

### With valid token
- [ ] protected task routes succeed

### With invalid token
- [ ] protected task routes fail

---

# Step 13 — Decide Whether Task Access Uses Current User Yet

This is an important design checkpoint.

At minimum for Phase 1:
- [ ] protect task routes so only authenticated users can access them

Optional improvement during Phase 1:
- [ ] tie task operations to the currently authenticated user

Examples of this improvement:
- [ ] only create tasks for the logged-in user
- [ ] only list tasks belonging to the logged-in user
- [ ] only complete tasks owned by the logged-in user

If you do not implement ownership rules yet, that is okay for early Phase 1, but you should decide consciously.

## Verify your decision

Choose one:
- [ ] "Phase 1 only adds authentication; permissions come later"
- [ ] "Phase 1 adds basic authentication + user-task ownership enforcement"

Write this decision down before coding further.

---

# Step 14 — Validate Layer Responsibilities

At this point, pause and inspect architecture discipline.

## Routes checklist

Routes should:
- [ ] accept request bodies
- [ ] inject dependencies
- [ ] call services
- [ ] return responses

Routes should not:
- [ ] query DB directly
- [ ] verify passwords directly
- [ ] create/decode JWT directly

## Services checklist

Services should:
- [ ] implement login logic
- [ ] orchestrate repository + password + JWT utility
- [ ] handle auth-related business decisions

Services should not:
- [ ] define HTTP routes
- [ ] perform raw DB queries directly if repository exists

## Repositories checklist

Repositories should:
- [ ] fetch user by email
- [ ] fetch user by id

Repositories should not:
- [ ] know about JWT
- [ ] know about headers
- [ ] verify passwords

## JWT utility checklist

JWT utility should:
- [ ] create token
- [ ] decode token
- [ ] validate token structure/expiration

JWT utility should not:
- [ ] query DB
- [ ] contain route logic

If any layer is doing too much, refactor before continuing.

---

# Step 15 — Full End-to-End Auth Test Checklist

Run these tests in order.

## Registration tests
- [ ] register user successfully
- [ ] duplicate email is handled correctly if you support uniqueness checks

## Login tests
- [ ] valid email + valid password returns token
- [ ] valid email + wrong password fails
- [ ] invalid email fails
- [ ] response shape matches token schema

## Token tests
- [ ] token is returned as string
- [ ] token type is bearer
- [ ] token can be used in Swagger authorize flow if you choose to test there

## Protected route tests
- [ ] no token -> unauthorized
- [ ] malformed header -> unauthorized
- [ ] invalid token -> unauthorized
- [ ] valid token -> success

## Current user tests
- [ ] token correctly maps back to DB user
- [ ] deleted/nonexistent user referenced by token is rejected

## Regression tests
- [ ] registration still works after auth changes
- [ ] existing routes still import correctly
- [ ] app still starts cleanly

---

# Step 16 — Clean Up Naming and Organization

Before ending Phase 1, tidy up any naming issues.

## Recommended route grouping

- [ ] registration belongs under auth if you want cleaner API grouping
- [ ] login belongs under auth
- [ ] current-user endpoint belongs under auth

## Recommended file grouping

- [ ] password hashing and JWT helpers belong under security utilities
- [ ] login schemas belong in auth schema module
- [ ] login business logic belongs in auth service module

## Verify

- [ ] authentication concepts are not scattered randomly across many unrelated files
- [ ] auth logic is easy to find by folder and filename

---

# Step 17 — Swagger / API Docs Verification

Since you are learning, this is important.

## Check in Swagger docs

- [ ] login endpoint appears correctly
- [ ] protected endpoint appears correctly
- [ ] request body schemas display correctly
- [ ] response schema displays correctly

## If you configure bearer auth in docs later
- [ ] Swagger authorize supports token entry
- [ ] protected endpoints can be tested from docs

This is optional for now, but useful.

---

# Step 18 — Security Sanity Checklist

Before declaring Phase 1 done, verify these basic security principles.

- [ ] plaintext password is never stored
- [ ] plaintext password is never returned in response
- [ ] JWT secret is not hardcoded in route/service files
- [ ] expired tokens are rejected
- [ ] invalid tokens are rejected
- [ ] protected routes do not allow anonymous access
- [ ] auth failures return proper unauthorized responses
- [ ] token payload does not include sensitive information

---

# Step 19 — Definition of Done for Phase 1

Phase 1 is complete only if **all** of these are true:

- [ ] user can register
- [ ] user can log in with email/password
- [ ] successful login returns JWT access token
- [ ] you have a reusable current-user dependency
- [ ] at least one protected endpoint works
- [ ] protected endpoints fail without valid bearer token
- [ ] selected real endpoints are protected
- [ ] config contains centralized JWT settings
- [ ] repository supports user lookup by email and by id
- [ ] auth logic is cleanly separated into proper layers

If one of these is missing, Phase 1 is not fully complete.

---

# Step 20 — Suggested Build Order Summary

Follow this exact order:

1. [ ] extend config for JWT settings
2. [ ] update `.env`
3. [ ] add repository method: get user by email
4. [ ] add repository method: get user by id
5. [ ] create auth schemas
6. [ ] create JWT utility
7. [ ] create auth service
8. [ ] create login route
9. [ ] register auth router in app
10. [ ] test registration + login
11. [ ] create current-user dependency
12. [ ] create one protected test endpoint
13. [ ] test valid/invalid/missing token behavior
14. [ ] protect real task endpoints
15. [ ] run full end-to-end auth verification
16. [ ] clean up structure and naming

---

# Common Mistakes to Avoid

- [ ] putting login logic inside the route
- [ ] putting JWT logic inside repository
- [ ] hardcoding secret in multiple places
- [ ] skipping "get user by id" and trying to use token alone as the full user object
- [ ] protecting all endpoints before testing one protected endpoint first
- [ ] confusing authentication with authorization
- [ ] trying to add roles/permissions before basic JWT auth works
- [ ] returning full user ORM objects from login when all you need is token response
- [ ] mixing registration schema and login schema into one object

---

# Final Result You Should Have

At the end of this phase, your project should conceptually include:

## Existing
- [ ] user model
- [ ] registration route
- [ ] password hashing
- [ ] DB session dependency

## New
- [ ] auth config values
- [ ] login request schema
- [ ] token response schema
- [ ] user lookup by email
- [ ] user lookup by id
- [ ] JWT utility
- [ ] auth service
- [ ] login route
- [ ] current-user dependency
- [ ] protected test endpoint
- [ ] protected task endpoints

---

# After Phase 1

Only after this phase is stable should you move to the next major feature area:

- boards
- lists
- cards
- roles
- activity feed

Do **not** start boards/lists/cards until JWT auth is working cleanly.

---