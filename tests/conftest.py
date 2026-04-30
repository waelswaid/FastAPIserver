import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Generate a test RSA key pair for JWT signing
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_test_public_pem = _test_private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

# Set test environment variables BEFORE any app imports
# TEST_DATABASE_URL takes precedence so in-container test runs can target a
# different database than the app's runtime DATABASE_URL.
_test_db_url = os.environ.get("TEST_DATABASE_URL")
if _test_db_url:
    os.environ["DATABASE_URL"] = _test_db_url
else:
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postpostgres23582358@localhost:5432/fastapiapp_test")
os.environ["JWT_PRIVATE_KEY"] = _test_private_pem
os.environ["JWT_PUBLIC_KEY"] = _test_public_pem
os.environ["JWT_ALGORITHM"] = "RS256"
os.environ.pop("JWT_SECRET_KEY", None)
os.environ["MAILGUN_API_KEY"] = "test-key"
os.environ["MAILGUN_DOMAIN"] = "test.mailgun.org"
os.environ["MAILGUN_FROM_EMAIL"] = "test@test.mailgun.org"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "development"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/api/auth/google/callback"
os.environ["OAUTH_FRONTEND_REDIRECT_URL"] = "http://localhost:5173"

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.models.base import Base
from app.database.session import get_db
from app.main import app
from app.models.user import User
from app.models.oauth_account import OAuthAccount  # noqa: F401 — register table
from app.utils.security.password_hash import hash_password


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Make db.commit() create savepoints instead of real commits
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Replace the real Redis client with fakeredis for every test."""
    import fakeredis.aioredis
    import app.core.redis as redis_module

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis_client", fake)

    # Prevent lifespan from overwriting the fake client
    async def _noop():
        pass

    monkeypatch.setattr(redis_module, "init_redis", _noop)
    monkeypatch.setattr(redis_module, "close_redis", _noop)

    # Also patch the already-imported references in main
    import app.main as main_module
    monkeypatch.setattr(main_module, "init_redis", _noop)
    monkeypatch.setattr(main_module, "close_redis", _noop)
    yield fake


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_send_email():
    """Patch the email-sending functions where the service modules import them.
    Tests can assert on call_args.args == (to_email, code)."""
    mock = MagicMock()
    with patch("app.services.email_verification_service.send_verification_email", mock), \
         patch("app.services.password_service.send_password_reset_email", mock), \
         patch("app.services.admin_services.send_password_reset_email", mock), \
         patch("app.services.admin_services.send_invite_email", mock):
        yield mock


@pytest.fixture()
def create_test_user(db_session):
    def _create(
        email="user@example.com",
        password="securepassword123",
        first_name="Test",
        last_name="User",
        is_verified=True,
    ):
        user = User(
            id=uuid.uuid4(),
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            is_verified=is_verified,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.flush()
        return user, password

    return _create


@pytest.fixture()
def verified_user(create_test_user):
    return create_test_user(
        email="verified@example.com",
        password="verifiedpass123",
        is_verified=True,
    )


@pytest.fixture()
def unverified_user(create_test_user):
    return create_test_user(
        email="unverified@example.com",
        password="unverifiedpass123",
        is_verified=False,
    )


@pytest.fixture()
def auth_client(client, verified_user):
    user, password = verified_user
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]
    return client, access_token, user
