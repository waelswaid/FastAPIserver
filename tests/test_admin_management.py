import uuid


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _make_admin(client, create_test_user, email="admin@example.com", password="adminpass123"):
    user, password = create_test_user(email=email, password=password)
    user.role = "admin"
    resp = _login(client, email, password)
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return user, password, token


# =====================================================================
# Disable user
# =====================================================================


def test_admin_disable_user_success(client, create_test_user):
    admin, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="target@example.com")

    resp = client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "User disabled"


def test_disabled_user_cannot_login(client, create_test_user):
    admin, _, admin_token = _make_admin(client, create_test_user)
    target, target_pass = create_test_user(email="target@example.com")

    client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )

    resp = _login(client, target.email, target_pass)
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


def test_disabled_user_tokens_rejected(client, create_test_user):
    admin, _, admin_token = _make_admin(client, create_test_user)
    target, target_pass = create_test_user(email="target@example.com")

    # get a valid token for target
    resp = _login(client, target.email, target_pass)
    target_token = resp.json()["access_token"]

    # verify it works
    resp = client.get("/api/users/me", headers=_auth_header(target_token))
    assert resp.status_code == 200

    # disable the user
    client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )

    # token should now be rejected
    resp = client.get("/api/users/me", headers=_auth_header(target_token))
    assert resp.status_code == 401


def test_admin_enable_user_success(client, create_test_user):
    admin, _, admin_token = _make_admin(client, create_test_user)
    target, target_pass = create_test_user(email="target@example.com")

    # disable
    client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )

    # enable
    resp = client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": False},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "User enabled"

    # user can log in again
    resp = _login(client, target.email, target_pass)
    assert resp.status_code == 200


def test_admin_cannot_disable_self(client, create_test_user):
    admin, _, admin_token = _make_admin(client, create_test_user)

    resp = client.patch(
        f"/api/admin/users/{admin.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 400
    assert "Cannot disable your own account" in resp.json()["detail"]


def test_disable_nonexistent_user_returns_404(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)

    resp = client.patch(
        f"/api/admin/users/{uuid.uuid4()}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 404


def test_disable_already_disabled_returns_400(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="target@example.com")

    client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )

    resp = client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 400
    assert "already disabled" in resp.json()["detail"]


def test_enable_already_enabled_returns_400(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="target@example.com")

    resp = client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": False},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 400
    assert "not disabled" in resp.json()["detail"]


def test_disable_forbidden_for_regular_user(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    regular, regular_pass = create_test_user(email="regular@example.com")
    target, _ = create_test_user(email="target@example.com")

    resp = _login(client, regular.email, regular_pass)
    regular_token = resp.json()["access_token"]

    resp = client.patch(
        f"/api/admin/users/{target.id}/status",
        json={"is_disabled": True},
        headers=_auth_header(regular_token),
    )
    assert resp.status_code == 403


# =====================================================================
# Force password reset
# =====================================================================


def test_admin_force_password_reset_success(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="target@example.com")

    resp = client.post(
        f"/api/admin/users/{target.id}/force-password-reset",
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password reset email sent"
    assert mock_send_email.called


def test_force_reset_invalidates_tokens(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, target_pass = create_test_user(email="target@example.com")

    # get a valid token for target
    resp = _login(client, target.email, target_pass)
    target_token = resp.json()["access_token"]

    # verify it works
    resp = client.get("/api/users/me", headers=_auth_header(target_token))
    assert resp.status_code == 200

    # admin forces reset
    client.post(
        f"/api/admin/users/{target.id}/force-password-reset",
        headers=_auth_header(admin_token),
    )

    # old token should be rejected
    resp = client.get("/api/users/me", headers=_auth_header(target_token))
    assert resp.status_code == 401


def test_force_reset_user_can_reset_via_code(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="target@example.com")

    client.post(
        f"/api/admin/users/{target.id}/force-password-reset",
        headers=_auth_header(admin_token),
    )

    code = mock_send_email.call_args.args[1]

    # validate the code
    resp = client.get(f"/api/auth/reset-password?code={code}")
    assert resp.status_code == 200

    # reset password using the code
    new_password = "newpassword123"
    resp = client.post(
        "/api/auth/reset-password",
        json={"code": code, "new_password": new_password},
    )
    assert resp.status_code == 200

    # can login with new password
    resp = _login(client, target.email, new_password)
    assert resp.status_code == 200


def test_force_reset_nonexistent_user_returns_404(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)

    resp = client.post(
        f"/api/admin/users/{uuid.uuid4()}/force-password-reset",
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 404


def test_force_reset_forbidden_for_regular_user(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    regular, regular_pass = create_test_user(email="regular@example.com")
    target, _ = create_test_user(email="target@example.com")

    resp = _login(client, regular.email, regular_pass)
    regular_token = resp.json()["access_token"]

    resp = client.post(
        f"/api/admin/users/{target.id}/force-password-reset",
        headers=_auth_header(regular_token),
    )
    assert resp.status_code == 403


# =====================================================================
# Invite user
# =====================================================================


def _extract_invite_code(mock_send_email):
    return mock_send_email.call_args.args[1]


def test_admin_invite_user_success(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    resp = client.post(
        "/api/admin/users/invite",
        json={"email": "newinvite@example.com"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["message"] == "Invitation sent"
    assert mock_send_email.called


def test_admin_invite_duplicate_real_account_returns_409(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    target, _ = create_test_user(email="existing@example.com")

    resp = client.post(
        "/api/admin/users/invite",
        json={"email": "existing@example.com"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 409


def test_admin_reinvite_pending_user_resends(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    # first invite
    client.post(
        "/api/admin/users/invite",
        json={"email": "pending@example.com"},
        headers=_auth_header(admin_token),
    )
    first_code = _extract_invite_code(mock_send_email)

    # second invite (resend)
    resp = client.post(
        "/api/admin/users/invite",
        json={"email": "pending@example.com"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 201
    second_code = _extract_invite_code(mock_send_email)

    # new code should be different
    assert first_code != second_code


def test_admin_invite_forbidden_for_regular_user(client, create_test_user):
    _, _, admin_token = _make_admin(client, create_test_user)
    regular, regular_pass = create_test_user(email="regular@example.com")

    resp = _login(client, regular.email, regular_pass)
    regular_token = resp.json()["access_token"]

    resp = client.post(
        "/api/admin/users/invite",
        json={"email": "someone@example.com"},
        headers=_auth_header(regular_token),
    )
    assert resp.status_code == 403


def test_accept_invite_success(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "invited@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    resp = client.post(
        "/api/auth/accept-invite",
        json={
            "code": code,
            "first_name": "Invited",
            "last_name": "User",
            "password": "invitedpass123",
        },
    )
    assert resp.status_code == 200
    assert "activated" in resp.json()["message"]

    # can log in
    resp = _login(client, "invited@example.com", "invitedpass123")
    assert resp.status_code == 200


def test_accept_invite_invalid_code_returns_400(client):
    resp = client.post(
        "/api/auth/accept-invite",
        json={
            "code": "00000000-0000-0000-0000-000000000000",
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 400


def test_accept_invite_expired_code_returns_400(client, create_test_user, mock_send_email, db_session):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "expired@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    # expire the action manually
    from app.models.pending_action import PendingAction
    from datetime import datetime, timezone, timedelta
    action = db_session.query(PendingAction).filter(PendingAction.code == code).first()
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.flush()

    resp = client.post(
        "/api/auth/accept-invite",
        json={
            "code": code,
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 400


def test_accept_invite_already_accepted_returns_400(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "double@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    # accept once
    client.post(
        "/api/auth/accept-invite",
        json={
            "code": code,
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        },
    )

    # try to accept again (code is deleted, so invalid)
    resp = client.post(
        "/api/auth/accept-invite",
        json={
            "code": code,
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 400


def test_invited_user_cannot_login_before_accepting(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "nologin@example.com"},
        headers=_auth_header(admin_token),
    )

    resp = _login(client, "nologin@example.com", "anypassword123")
    assert resp.status_code == 401


# =====================================================================
# Validate invite code (GET)
# =====================================================================


def test_validate_invite_code_success(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "validate@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    resp = client.get(f"/api/auth/accept-invite?code={code}")
    assert resp.status_code == 200
    assert resp.json()["code"] == code


def test_validate_invite_code_invalid_returns_400(client):
    resp = client.get(f"/api/auth/accept-invite?code=00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 400


def test_validate_invite_code_expired_returns_400(client, create_test_user, mock_send_email, db_session):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "expvalidate@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    from app.models.pending_action import PendingAction
    from datetime import datetime, timezone, timedelta
    action = db_session.query(PendingAction).filter(PendingAction.code == code).first()
    action.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.flush()

    resp = client.get(f"/api/auth/accept-invite?code={code}")
    assert resp.status_code == 400


def test_validate_invite_code_already_accepted_returns_400(client, create_test_user, mock_send_email):
    _, _, admin_token = _make_admin(client, create_test_user)

    client.post(
        "/api/admin/users/invite",
        json={"email": "acceptedvalidate@example.com"},
        headers=_auth_header(admin_token),
    )
    code = _extract_invite_code(mock_send_email)

    client.post(
        "/api/auth/accept-invite",
        json={
            "code": code,
            "first_name": "Test",
            "last_name": "User",
            "password": "testpass123",
        },
    )

    resp = client.get(f"/api/auth/accept-invite?code={code}")
    assert resp.status_code == 400
