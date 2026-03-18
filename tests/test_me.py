from datetime import datetime, timezone, timedelta

from app.models.token_blacklist import TokenBlacklist
from app.services.auth_services import jwt_gen


# Valid access token returns 200 with correct user data
def test_get_me_success(auth_client):
    client, access_token, user = auth_client
    resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == user.email
    assert data["first_name"] == user.first_name
    assert data["last_name"] == user.last_name


# No Authorization header returns 401
def test_get_me_no_token(client):
    resp = client.get("/api/users/me")
    assert resp.status_code == 401


# Malformed token returns 401
def test_get_me_invalid_token(client):
    resp = client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer garbage"},
    )
    assert resp.status_code == 401


# Access token with blacklisted JTI returns 401
def test_get_me_blacklisted_token(auth_client, db_session):
    client, access_token, user = auth_client
    payload = jwt_gen.decode_access_token(access_token)
    db_session.add(
        TokenBlacklist(
            jti=payload["jti"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()

    resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401


# Access token issued before password change is rejected (401)
def test_get_me_token_before_password_change(auth_client, db_session):
    client, access_token, user = auth_client
    user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    db_session.flush()

    resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401
