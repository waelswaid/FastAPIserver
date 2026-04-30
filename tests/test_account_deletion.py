from app.repositories.user_repository import find_user_by_id
from app.repositories.pending_action_repository import upsert_action, find_action_by_user_and_type
from datetime import datetime, timezone, timedelta


def test_delete_account_success(auth_client, db_session):
    client, access_token, user = auth_client
    user_id = user.id

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "verifiedpass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    assert find_user_by_id(db_session, user_id) is None


def test_delete_account_wrong_password(auth_client):
    client, access_token, user = auth_client

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "wrongpassword123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect password"


def test_delete_account_unauthenticated(client):
    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "somepassword123"},
    )
    assert resp.status_code == 401


def test_delete_account_token_invalidated(auth_client):
    client, access_token, user = auth_client

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "verifiedpass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    me_resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 401


def test_delete_account_pending_actions_cleaned(auth_client, db_session):
    client, access_token, user = auth_client

    upsert_action(
        db_session,
        user.id,
        "email_verification_code",
        "test-code-123",
        datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert find_action_by_user_and_type(db_session, user.id, "email_verification_code") is not None

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "verifiedpass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    assert find_action_by_user_and_type(db_session, user.id, "email_verification_code") is None


def test_delete_account_email_reusable(auth_client, db_session):
    client, access_token, user = auth_client
    email = user.email

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "verifiedpass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    register_resp = client.post(
        "/api/users",
        json={
            "first_name": "New",
            "last_name": "User",
            "email": email,
            "password": "newpassword123",
        },
    )
    assert register_resp.status_code == 200


def test_delete_account_password_too_short(auth_client):
    client, access_token, user = auth_client

    resp = client.request(
        "DELETE",
        "/api/users/me",
        json={"password": "short"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 422
