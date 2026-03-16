import os

# Set test environment variables BEFORE any app imports
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/fastapiapp_test"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["MAILGUN_API_KEY"] = "test-key"
os.environ["MAILGUN_DOMAIN"] = "test.mailgun.org"
os.environ["MAILGUN_FROM_EMAIL"] = "test@test.mailgun.org"

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
from app.utils.security.password_hash import hash_password
from app.api.dependencies.rate_limiter import (
    forgot_password_limiter,
    resend_verification_limiter,
    reset_password_limiter,
)


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
    with patch("app.utils.email.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    forgot_password_limiter._hits.clear()
    resend_verification_limiter._hits.clear()
    reset_password_limiter._hits.clear()


@pytest.fixture()
def create_test_user(db_session):
    def _create(
        email="user@example.com",
        password="securepassword123",
        name="Test User",
        is_verified=True,
    ):
        user = User(
            id=uuid.uuid4(),
            name=name,
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
