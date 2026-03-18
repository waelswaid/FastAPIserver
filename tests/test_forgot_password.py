import requests

from app.models.pending_action import PendingAction
from app.services.auth_services import ACTION_PASSWORD_RESET_CODE, ACTION_PASSWORD_RESET_JTI


# Verified user's email triggers a reset email (200, email sent)
def test_forgot_password_existing_email(client, verified_user, mock_send_email):
    user, _ = verified_user
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": user.email},
    )
    assert resp.status_code == 200
    mock_send_email.assert_called_once()


# Non-existent email returns 200 but no email is sent (no info leakage)
def test_forgot_password_nonexistent_email(client, mock_send_email):
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


# Unverified user returns 200 but no email is sent
def test_forgot_password_unverified_user(client, unverified_user, mock_send_email):
    user, _ = unverified_user
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": user.email},
    )
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


# Mailgun failure returns 503
def test_forgot_password_email_failure(client, verified_user, mock_send_email):
    user, _ = verified_user
    mock_send_email.return_value.raise_for_status.side_effect = requests.RequestException("fail")
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": user.email},
    )
    assert resp.status_code == 503


# Second forgot-password request invalidates the first code and token
def test_forgot_password_second_request_invalidates_first_token(
    client, verified_user, db_session
):
    user, _ = verified_user

    client.post("/api/auth/forgot-password", json={"email": user.email})
    first_code_action = db_session.query(PendingAction).filter(
        PendingAction.user_id == user.id,
        PendingAction.action_type == ACTION_PASSWORD_RESET_CODE,
    ).first()
    first_jti_action = db_session.query(PendingAction).filter(
        PendingAction.user_id == user.id,
        PendingAction.action_type == ACTION_PASSWORD_RESET_JTI,
    ).first()
    assert first_code_action is not None
    assert first_jti_action is not None
    first_code = first_code_action.code

    client.post("/api/auth/forgot-password", json={"email": user.email})
    db_session.expire_all()
    second_code_action = db_session.query(PendingAction).filter(
        PendingAction.user_id == user.id,
        PendingAction.action_type == ACTION_PASSWORD_RESET_CODE,
    ).first()
    second_code = second_code_action.code
    assert second_code != first_code

    # First code no longer works
    resp = client.post(
        "/api/auth/reset-password",
        json={"code": first_code, "new_password": "newpassword123"},
    )
    assert resp.status_code == 400

    # Second code works
    resp2 = client.post(
        "/api/auth/reset-password",
        json={"code": second_code, "new_password": "newpassword123"},
    )
    assert resp2.status_code == 200
