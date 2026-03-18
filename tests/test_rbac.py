import uuid
from datetime import datetime, timezone, timedelta

from app.services.auth_services import jwt_gen


# --- Fixtures local to this module ---


def _login(client, email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# validate-token includes role
# =====================================================================


def test_validate_token_includes_role(auth_client):
    client, access_token, user = auth_client
    resp = client.get("/api/auth/validate-token", headers=_auth_header(access_token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


def test_validate_token_includes_admin_role(client, create_test_user):
    user, password = create_test_user(email="admin@example.com")
    user.role = "admin"
    resp = client.post("/api/auth/login", json={"email": user.email, "password": password})
    token = resp.json()["access_token"]
    resp = client.get("/api/auth/validate-token", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


# =====================================================================
# JWT contains role claim
# =====================================================================


def test_login_jwt_contains_role_claim(client, verified_user):
    user, password = verified_user
    token = _login(client, user.email, password)
    payload = jwt_gen.decode_access_token(token)
    assert payload["role"] == "user"


def test_login_admin_jwt_contains_admin_role(client, create_test_user):
    user, password = create_test_user(email="admin2@example.com")
    user.role = "admin"
    token = _login(client, user.email, password)
    payload = jwt_gen.decode_access_token(token)
    assert payload["role"] == "admin"


# =====================================================================
# role_changed_at invalidates access tokens
# =====================================================================


def test_access_token_rejected_after_role_change(auth_client, db_session):
    client, access_token, user = auth_client
    user.role_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    db_session.flush()

    resp = client.get("/api/users/me", headers=_auth_header(access_token))
    assert resp.status_code == 401


# =====================================================================
# role_changed_at invalidates refresh tokens
# =====================================================================


def test_refresh_rejected_after_role_change(client, verified_user, db_session):
    user, password = verified_user
    client.post("/api/auth/login", json={"email": user.email, "password": password})

    user.role_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    db_session.flush()

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


# =====================================================================
# require_role — admin endpoints reject regular users
# =====================================================================


def test_admin_list_users_forbidden_for_regular_user(auth_client):
    client, access_token, user = auth_client
    resp = client.get("/api/admin/users/", headers=_auth_header(access_token))
    assert resp.status_code == 403


def test_admin_change_role_forbidden_for_regular_user(auth_client):
    client, access_token, user = auth_client
    resp = client.patch(
        f"/api/admin/users/{user.id}/role",
        json={"role": "admin"},
        headers=_auth_header(access_token),
    )
    assert resp.status_code == 403


def test_admin_endpoints_reject_unauthenticated(client):
    resp = client.get("/api/admin/users/")
    assert resp.status_code == 401

    resp = client.patch(
        f"/api/admin/users/{uuid.uuid4()}/role",
        json={"role": "admin"},
    )
    assert resp.status_code == 401


# =====================================================================
# Admin: list users
# =====================================================================


def test_admin_list_users_success(client, create_test_user):
    admin, admin_pw = create_test_user(email="listadmin@example.com")
    admin.role = "admin"

    create_test_user(email="regular1@example.com")
    create_test_user(email="regular2@example.com")

    token = _login(client, admin.email, admin_pw)
    resp = client.get("/api/admin/users/", headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_admin_list_users_filter_by_role(client, create_test_user):
    admin, admin_pw = create_test_user(email="filteradmin@example.com")
    admin.role = "admin"

    create_test_user(email="filtereduser@example.com")

    token = _login(client, admin.email, admin_pw)

    resp = client.get("/api/admin/users/?role=admin", headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["role"] == "admin" for u in data)

    resp = client.get("/api/admin/users/?role=user", headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["role"] == "user" for u in data)


def test_admin_list_users_pagination(client, create_test_user):
    admin, admin_pw = create_test_user(email="pageadmin@example.com")
    admin.role = "admin"

    for i in range(5):
        create_test_user(email=f"page{i}@example.com")

    token = _login(client, admin.email, admin_pw)
    resp = client.get("/api/admin/users/?skip=0&limit=2", headers=_auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# =====================================================================
# Admin: change role
# =====================================================================


def test_admin_change_role_success(client, create_test_user, db_session):
    admin, admin_pw = create_test_user(email="roleadmin@example.com")
    admin.role = "admin"

    target, _ = create_test_user(email="target@example.com")

    token = _login(client, admin.email, admin_pw)
    resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        json={"role": "admin"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    db_session.refresh(target)
    assert target.role == "admin"
    assert target.role_changed_at is not None


def test_admin_change_role_same_role_returns_400(client, create_test_user):
    admin, admin_pw = create_test_user(email="sameadmin@example.com")
    admin.role = "admin"

    target, _ = create_test_user(email="sametarget@example.com")

    token = _login(client, admin.email, admin_pw)
    resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        json={"role": "user"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 400


def test_admin_change_role_invalid_role_returns_422(client, create_test_user):
    admin, admin_pw = create_test_user(email="invaladmin@example.com")
    admin.role = "admin"

    target, _ = create_test_user(email="invaltarget@example.com")

    token = _login(client, admin.email, admin_pw)
    resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        json={"role": "superadmin"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 422


def test_admin_change_role_nonexistent_user_returns_404(client, create_test_user):
    admin, admin_pw = create_test_user(email="404admin@example.com")
    admin.role = "admin"

    token = _login(client, admin.email, admin_pw)
    resp = client.patch(
        f"/api/admin/users/{uuid.uuid4()}/role",
        json={"role": "admin"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 404


# =====================================================================
# Role change invalidates target user's tokens
# =====================================================================


def test_role_change_invalidates_target_tokens(client, create_test_user, db_session):
    admin, admin_pw = create_test_user(email="invadmin@example.com")
    admin.role = "admin"

    target, target_pw = create_test_user(email="invtarget@example.com")

    # target logs in and gets a token
    target_token = _login(client, target.email, target_pw)

    # admin changes target's role
    admin_token = _login(client, admin.email, admin_pw)
    resp = client.patch(
        f"/api/admin/users/{target.id}/role",
        json={"role": "admin"},
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 200

    # target's old token should now be rejected
    resp = client.get("/api/users/me", headers=_auth_header(target_token))
    assert resp.status_code == 401


# =====================================================================
# Default role for new users
# =====================================================================


def test_new_user_defaults_to_user_role(client, create_test_user):
    user, _ = create_test_user(email="default@example.com")
    assert user.role == "user"


def test_registered_user_has_user_role(client, db_session):
    resp = client.post(
        "/api/users/create",
        json={"first_name": "New", "last_name": "User", "email": "newreg@example.com", "password": "securepassword123"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"
