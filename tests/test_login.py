# Valid credentials return 200 with access_token in body and refresh_token cookie
def test_login_success(client, verified_user):
    user, password = verified_user
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in resp.cookies


# Unverified user is rejected with 403
def test_login_unverified_user(client, unverified_user):
    user, password = unverified_user
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 403


# Wrong password returns 401
def test_login_wrong_password(client, verified_user):
    user, _ = verified_user
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "wrongpassword123"},
    )
    assert resp.status_code == 401


# Non-existent email returns 401
def test_login_nonexistent_email(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "somepassword123"},
    )
    assert resp.status_code == 401


# Password below minimum length is rejected at schema level (422)
def test_login_short_password_rejected(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "short"},
    )
    assert resp.status_code == 422


# Refresh token cookie has httponly and samesite=strict flags
def test_login_cookie_security_flags(client, verified_user):
    user, password = verified_user
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    cookie_header = resp.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()
    assert "samesite=strict" in cookie_header.lower()
