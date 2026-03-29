import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

import pytest

from app.models.user import User
from app.models.oauth_account import OAuthAccount
from app.utils.security.password_hash import hash_password


GOOGLE_USERINFO = {
    "sub": "google-uid-123456",
    "email": "oauth@example.com",
    "given_name": "Jane",
    "family_name": "Doe",
    "email_verified": True,
}


def _mock_google_api(userinfo=None):
    """Return a patcher that mocks both the token exchange and userinfo requests."""
    info = userinfo or GOOGLE_USERINFO

    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "oauth2.googleapis.com/token" in url:
            resp.json.return_value = {"access_token": "google-access-token"}
        return resp

    def get_side_effect(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "oauth2/v3/userinfo" in url:
            resp.json.return_value = info
        return resp

    post_patcher = patch("app.services.oauth_service.http_requests.post", side_effect=side_effect)
    get_patcher = patch("app.services.oauth_service.http_requests.get", side_effect=get_side_effect)
    return post_patcher, get_patcher


def _extract_token_from_redirect(resp):
    """Extract the access token from the redirect URL query params."""
    location = resp.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    return params["token"][0]


# --- Redirect ---

def test_google_redirect(client):
    resp = client.get("/api/auth/google", follow_redirects=False)
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]
    assert "client_id=" in resp.headers["location"]


# --- Callback: new user ---

def test_google_callback_creates_new_user(client, db_session):
    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code", follow_redirects=False)

    assert resp.status_code == 307
    assert "token=" in resp.headers["location"]
    assert "refresh_token" in resp.cookies

    user = db_session.query(User).filter(User.email == "oauth@example.com").first()
    assert user is not None
    assert user.first_name == "Jane"
    assert user.last_name == "Doe"
    assert user.is_verified is True
    assert user.password_hash == "!oauth"

    oauth = db_session.query(OAuthAccount).filter(OAuthAccount.user_id == user.id).first()
    assert oauth is not None
    assert oauth.provider == "google"
    assert oauth.provider_user_id == "google-uid-123456"


# --- Callback: existing user same email, links OAuth ---

def test_google_callback_links_existing_user(client, db_session, create_test_user):
    user, _ = create_test_user(email="oauth@example.com", password="existingpass123")

    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code", follow_redirects=False)

    assert resp.status_code == 307
    assert "token=" in resp.headers["location"]

    oauth = db_session.query(OAuthAccount).filter(OAuthAccount.user_id == user.id).first()
    assert oauth is not None
    assert oauth.provider == "google"


# --- Callback: existing OAuth link logs in directly ---

def test_google_callback_existing_oauth_account(client, db_session, create_test_user):
    user, _ = create_test_user(email="oauth@example.com", password="existingpass123")
    oauth = OAuthAccount(
        user_id=user.id,
        provider="google",
        provider_user_id="google-uid-123456",
    )
    db_session.add(oauth)
    db_session.flush()

    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code", follow_redirects=False)

    assert resp.status_code == 307
    assert "token=" in resp.headers["location"]


# --- Callback: disabled user rejected ---

def test_google_callback_disabled_user(client, db_session, create_test_user):
    user, _ = create_test_user(email="oauth@example.com", password="existingpass123")
    user.is_disabled = True
    db_session.flush()

    oauth = OAuthAccount(
        user_id=user.id,
        provider="google",
        provider_user_id="google-uid-123456",
    )
    db_session.add(oauth)
    db_session.flush()

    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code")

    assert resp.status_code == 403


# --- Callback: disabled user (found by email, no prior OAuth link) ---

def test_google_callback_disabled_user_by_email(client, db_session, create_test_user):
    user, _ = create_test_user(email="oauth@example.com", password="existingpass123")
    user.is_disabled = True
    db_session.flush()

    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code")

    assert resp.status_code == 403


# --- Callback: unverified user becomes verified via OAuth ---

def test_google_callback_verifies_unverified_user(client, db_session, create_test_user):
    user, _ = create_test_user(
        email="oauth@example.com",
        password="existingpass123",
        is_verified=False,
    )

    post_patch, get_patch = _mock_google_api()
    with post_patch, get_patch:
        resp = client.get("/api/auth/google/callback?code=test-auth-code", follow_redirects=False)

    assert resp.status_code == 307
    db_session.refresh(user)
    assert user.is_verified is True


# --- Callback: token exchange failure ---

def test_google_callback_token_exchange_failure(client):
    def fail_post(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 400
        resp.json.return_value = {"error": "invalid_grant"}
        return resp

    with patch("app.services.oauth_service.http_requests.post", side_effect=fail_post):
        resp = client.get("/api/auth/google/callback?code=bad-code")

    assert resp.status_code == 400


# --- Callback: missing code param ---

def test_google_callback_missing_code(client):
    resp = client.get("/api/auth/google/callback")
    assert resp.status_code == 422


# --- Change password blocked for OAuth-only user ---

def test_change_password_blocked_for_oauth_user(client, db_session):
    user = User(
        id=uuid.uuid4(),
        first_name="OAuth",
        last_name="User",
        email="oauthonly@example.com",
        password_hash="!oauth",
        is_verified=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.flush()

    login_post_patch, login_get_patch = _mock_google_api(
        userinfo={**GOOGLE_USERINFO, "email": "oauthonly@example.com"}
    )
    with login_post_patch, login_get_patch:
        login_resp = client.get("/api/auth/google/callback?code=test-code", follow_redirects=False)
    token = _extract_token_from_redirect(login_resp)

    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "anything123", "new_password": "newpassword123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "OAuth" in resp.json()["detail"]


# --- Delete account blocked for OAuth-only user ---

def test_delete_account_blocked_for_oauth_user(client, db_session):
    user = User(
        id=uuid.uuid4(),
        first_name="OAuth",
        last_name="User",
        email="oauthdelete@example.com",
        password_hash="!oauth",
        is_verified=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.flush()

    login_post_patch, login_get_patch = _mock_google_api(
        userinfo={**GOOGLE_USERINFO, "email": "oauthdelete@example.com"}
    )
    with login_post_patch, login_get_patch:
        login_resp = client.get("/api/auth/google/callback?code=test-code", follow_redirects=False)
    token = _extract_token_from_redirect(login_resp)

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "anything123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "OAuth" in resp.json()["detail"]
