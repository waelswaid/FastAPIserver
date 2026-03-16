import requests


# Valid registration returns 200 with UserRead fields and sends verification email
def test_register_success(client, mock_send_email):
    resp = client.post(
        "/api/users/create",
        json={"name": "Alice", "email": "alice@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "created_at" in data
    mock_send_email.assert_called_once()


# Registering with an already-used email returns 409 Conflict
def test_register_duplicate_email(client, verified_user):
    user, _ = verified_user
    resp = client.post(
        "/api/users/create",
        json={"name": "Dup", "email": user.email, "password": "strongpass123"},
    )
    assert resp.status_code == 409


# Mailgun failure during registration returns 500 (user is created but email not sent)
def test_register_email_send_failure(client, mock_send_email):
    mock_send_email.return_value.raise_for_status.side_effect = requests.RequestException("fail")
    resp = client.post(
        "/api/users/create",
        json={"name": "Bob", "email": "bob@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 500


# Missing name field returns 422
def test_register_missing_name(client):
    resp = client.post(
        "/api/users/create",
        json={"email": "test@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 422


# Missing email field returns 422
def test_register_missing_email(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Test", "password": "strongpass123"},
    )
    assert resp.status_code == 422


# Missing password field returns 422
def test_register_missing_password(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Test", "email": "test@example.com"},
    )
    assert resp.status_code == 422


# Password under 8 characters returns 422
def test_register_short_password(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Test", "email": "test@example.com", "password": "short"},
    )
    assert resp.status_code == 422


# Password over 128 characters returns 422
def test_register_password_too_long(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Test", "email": "test@example.com", "password": "a" * 129},
    )
    assert resp.status_code == 422


# Malformed email address returns 422
def test_register_invalid_email_format(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Test", "email": "not-an-email", "password": "strongpass123"},
    )
    assert resp.status_code == 422


# Response body does not expose password_hash or password
def test_register_response_no_password_hash(client):
    resp = client.post(
        "/api/users/create",
        json={"name": "Safe", "email": "safe@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "password_hash" not in data
    assert "password" not in data


# Newly registered user cannot login until email is verified (403)
def test_register_user_cannot_login_before_verification(client):
    client.post(
        "/api/users/create",
        json={"name": "New", "email": "new@example.com", "password": "strongpass123"},
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "strongpass123"},
    )
    assert login_resp.status_code == 403
