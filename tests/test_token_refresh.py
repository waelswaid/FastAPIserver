from datetime import datetime, timezone, timedelta

from app.models.token_blacklist import TokenBlacklist
from app.services.auth_services import jwt_gen


# Valid refresh cookie returns 200 with a new access_token
def test_refresh_success(client, verified_user):
    user, password = verified_user
    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# Missing refresh cookie returns 401
def test_refresh_no_cookie(client):
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


# Garbage refresh cookie returns 401
def test_refresh_invalid_token(client):
    client.cookies.set("refresh_token", "garbage-token")
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


# Blacklisted refresh token JTI returns 401
def test_refresh_blacklisted_token(client, verified_user, db_session):
    user, password = verified_user
    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200

    refresh_token = client.cookies.get("refresh_token")
    payload = jwt_gen.decode_refresh_token(refresh_token)
    jti = payload["jti"]

    db_session.add(
        TokenBlacklist(jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    )
    db_session.flush()

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


# Refresh token issued before password change is rejected (401)
def test_refresh_after_password_change(client, verified_user, db_session):
    user, password = verified_user
    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200

    user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    db_session.flush()

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


# New access token from refresh is usable on /users/me
def test_refresh_new_token_works_on_me(client, verified_user):
    user, password = verified_user
    client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )

    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    new_token = refresh_resp.json()["access_token"]

    me_resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == user.email
