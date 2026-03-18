from datetime import datetime, timezone, timedelta

from app.models.token_blacklist import TokenBlacklist
from app.models.pending_action import PendingAction
from app.services.auth_services import jwt_gen, ACTION_EMAIL_VERIFICATION_CODE


# Valid verification code sets is_verified=True (200)
def test_verify_via_code_success(client, unverified_user, db_session):
    user, _ = unverified_user
    code = "test-verification-code"
    db_session.add(PendingAction(
        user_id=user.id,
        action_type=ACTION_EMAIL_VERIFICATION_CODE,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    db_session.flush()

    resp = client.get(f"/api/auth/verify-email?code={code}")
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.is_verified is True


# Bogus verification code returns 400
def test_verify_via_code_invalid(client):
    resp = client.get("/api/auth/verify-email?code=bogus-code")
    assert resp.status_code == 400


# Expired verification code returns 400
def test_verify_via_code_expired(client, unverified_user, db_session):
    user, _ = unverified_user
    code = "expired-verification-code"
    db_session.add(PendingAction(
        user_id=user.id,
        action_type=ACTION_EMAIL_VERIFICATION_CODE,
        code=code,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    db_session.flush()

    resp = client.get(f"/api/auth/verify-email?code={code}")
    assert resp.status_code == 400


# Code on an already-verified user returns 400
def test_verify_via_code_already_verified(client, verified_user, db_session):
    user, _ = verified_user
    code = "already-verified-code"
    db_session.add(PendingAction(
        user_id=user.id,
        action_type=ACTION_EMAIL_VERIFICATION_CODE,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    db_session.flush()

    resp = client.get(f"/api/auth/verify-email?code={code}")
    assert resp.status_code == 400


# Valid verification JWT sets is_verified=True (200)
def test_verify_via_token_success(client, unverified_user, db_session):
    user, _ = unverified_user
    token = jwt_gen.create_email_verification_token(str(user.id))

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.is_verified is True


# Expired verification JWT returns 400
def test_verify_via_token_expired(client, unverified_user, db_session):
    user, _ = unverified_user
    import jwt as pyjwt
    from app.core.config import settings

    payload = {
        "sub": str(user.id),
        "type": "email_verification",
        "iat": datetime.now(timezone.utc) - timedelta(hours=25),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "jti": "expired-verify-jti",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 400


# Verification JWT for an already-verified user returns 400
def test_verify_via_token_already_verified(client, verified_user, db_session):
    user, _ = verified_user
    token = jwt_gen.create_email_verification_token(str(user.id))

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 400


# Verification JWT whose JTI is blacklisted returns 400
def test_verify_via_token_blacklisted_jti(client, unverified_user, db_session):
    user, _ = unverified_user
    token = jwt_gen.create_email_verification_token(str(user.id))
    payload = jwt_gen.decode_email_verification_token(token)

    db_session.add(
        TokenBlacklist(
            jti=payload["jti"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 400


# End-to-end: register -> verify via code -> login succeeds
def test_verify_then_login_works(client, db_session):
    client.post(
        "/api/users/create",
        json={"first_name": "Flow", "last_name": "User", "email": "flow@example.com", "password": "flowpass1234"},
    )

    login_resp = client.post(
        "/api/auth/login",
        json={"email": "flow@example.com", "password": "flowpass1234"},
    )
    assert login_resp.status_code == 403

    from app.models.user import User
    user = db_session.query(User).filter(User.email == "flow@example.com").first()
    action = db_session.query(PendingAction).filter(
        PendingAction.user_id == user.id,
        PendingAction.action_type == ACTION_EMAIL_VERIFICATION_CODE,
    ).first()
    assert action is not None
    code = action.code

    verify_resp = client.get(f"/api/auth/verify-email?code={code}")
    assert verify_resp.status_code == 200

    login_resp2 = client.post(
        "/api/auth/login",
        json={"email": "flow@example.com", "password": "flowpass1234"},
    )
    assert login_resp2.status_code == 200
