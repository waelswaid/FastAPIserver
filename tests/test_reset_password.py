from datetime import datetime, timezone, timedelta

from app.models.token_blacklist import TokenBlacklist
from app.services.auth_services import jwt_gen


# GET with valid reset code returns 200 and echoes the code back
def test_validate_reset_code_success(client, verified_user, db_session):
    user, _ = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code
    assert code is not None

    resp = client.get(f"/api/auth/reset-password?code={code}")
    assert resp.status_code == 200
    assert resp.json()["code"] == code


# GET with bogus code returns 400
def test_validate_reset_code_invalid(client):
    resp = client.get("/api/auth/reset-password?code=bogus-code")
    assert resp.status_code == 400


# GET with expired code returns 400
def test_validate_reset_code_expired(client, verified_user, db_session):
    user, _ = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code

    user.password_reset_code_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.flush()

    resp = client.get(f"/api/auth/reset-password?code={code}")
    assert resp.status_code == 400


# POST with valid code resets password; login with new password succeeds
def test_reset_password_via_code_success(client, verified_user, db_session):
    user, old_password = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code

    resp = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": "brandnewpass123"},
    )
    assert resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "brandnewpass123"},
    )
    assert login_resp.status_code == 200


# Reusing the same reset code a second time returns 400
def test_reset_password_via_code_reused(client, verified_user, db_session):
    user, _ = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code

    resp1 = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": "newpassword123"},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": "anotherpass123"},
    )
    assert resp2.status_code == 400


# POST with valid reset JWT (and matching JTI on user) returns 200
def test_reset_password_via_token_success(client, verified_user, db_session):
    user, _ = verified_user
    token = jwt_gen.create_password_reset_token(str(user.id))
    payload = jwt_gen.decode_password_reset_token(token)

    user.password_reset_jti = payload["jti"]
    user.password_reset_jti_expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db_session.flush()

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "tokenreset123"},
    )
    assert resp.status_code == 200


# Expired reset JWT returns 400
def test_reset_password_via_token_expired(client, verified_user, db_session):
    user, _ = verified_user
    import jwt as pyjwt
    from app.core.config import settings

    payload = {
        "sub": str(user.id),
        "type": "password_reset",
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "jti": "expired-jti",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


# Reset JWT whose JTI is in the blacklist returns 400
def test_reset_password_via_token_blacklisted(client, verified_user, db_session):
    user, _ = verified_user
    token = jwt_gen.create_password_reset_token(str(user.id))
    payload = jwt_gen.decode_password_reset_token(token)
    jti = payload["jti"]

    user.password_reset_jti = jti
    user.password_reset_jti_expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db_session.flush()

    db_session.add(
        TokenBlacklist(jti=jti, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    )
    db_session.flush()

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


# POST with neither token nor code returns 422 (schema validation)
def test_reset_password_missing_token_and_code(client):
    resp = client.post(
        "/api/auth/reset-password",
        json={"new_password": "newpassword123"},
    )
    assert resp.status_code == 422


# New password below minimum length returns 422
def test_reset_password_short_new_password(client, verified_user, db_session):
    user, _ = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code

    resp = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": "short"},
    )
    assert resp.status_code == 422


# POST with expired reset code returns 400
def test_reset_password_via_code_expired_post(client, verified_user, db_session):
    user, _ = verified_user
    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.refresh(user)
    code = user.password_reset_code

    user.password_reset_code_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.flush()

    resp = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


# Valid token whose JTI doesn't match the user's stored password_reset_jti returns 400
def test_reset_password_via_token_jti_mismatch(client, verified_user, db_session):
    user, _ = verified_user
    token = jwt_gen.create_password_reset_token(str(user.id))

    user.password_reset_jti = "some-other-jti"
    user.password_reset_jti_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.flush()

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


# Reset via token: new password works and old password is rejected
def test_reset_password_via_token_then_login(client, verified_user, db_session):
    user, old_password = verified_user
    token = jwt_gen.create_password_reset_token(str(user.id))
    payload = jwt_gen.decode_password_reset_token(token)

    user.password_reset_jti = payload["jti"]
    user.password_reset_jti_expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db_session.flush()

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "tokenreset999"},
    )
    assert resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "tokenreset999"},
    )
    assert login_resp.status_code == 200

    old_login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": old_password},
    )
    assert old_login_resp.status_code == 401
