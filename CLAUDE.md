# FastAPIapp — Claude Instructions

auth-system is a generic authentication system and must remain that way.

## Architecture & Modularity
- Strictly follow the service layer pattern: routes call services, services call repositories, repositories talk to the DB
- Never access the DB directly from routes or services — always go through a repository function
- Never put business logic in repository functions — they only read/write data
- Each model gets its own file in app/models/
- Each model gets its own repository file in app/repositories/

## Security
- Never log passwords, password hashes, raw tokens, reset codes, or verification codes
- Never expose JWT tokens or opaque codes in error messages
- Always use WITH FOR UPDATE (row-level locking) when reading a row you intend to update in the same transaction
- Rate limit all auth endpoints (login, register, reset)
- Always hash passwords with the existing hash_password utility before storing
- Auth endpoints must not leak whether an email exists — return identical responses for existing and non-existing emails on reset/verification flows

## Database & Migrations
- Always create an Alembic migration for every model change — never modify the DB manually
- All current database data is test/fake data and expendable. If a migration or schema change is simpler to implement with a clean DB, prefer   wiping and re-running          
  migrations over writing a complex data migration.
- Never store ephemeral/temporary data on the users table — use a dedicated table
- Always use timezone-aware datetimes (DateTime(timezone=True))
- Prefer nullable=False with server defaults over nullable=True where possible

## Error Handling
- Use HTTPException with appropriate status codes — never let SQLAlchemy or Python exceptions bubble up to the client
- 401 for auth failures, 403 for permission failures, 409 for duplicates, 404 for not found
- Catch IntegrityError at the repository layer and raise domain-specific exceptions (e.g. DuplicateEmailError)

## Logging
- All audit events must use the format: audit: event=<name> user_id=<id> [extra fields]
- Use logger.warning() for failed auth attempts, logger.info() for all other audit events
- Every service file must have: import logging / logger = logging.getLogger(__name__)

## General
- Do not add new dependencies without being asked — unless it's necessary, in that case ask for permission and explain why it's needed
- Do not create new files unless necessary — prefer extending existing ones
- Do not add docstrings or comments to code you didn't change
- Keep endpoints RESTful — resources are nouns, HTTP verbs express the action

## Tests
- Create tests for every new feature implemented that should be tested

## Readme.md
- Update readme.md when you're done if needed