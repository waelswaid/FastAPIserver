from unittest.mock import patch


# --- Existing endpoint tests ---


def test_forgot_password_rate_limit(client, verified_user):
    user, _ = verified_user
    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    resp = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 429


def test_resend_verification_rate_limit(client, unverified_user):
    user, _ = unverified_user
    for i in range(5):
        resp = client.post("/api/auth/resend-verification", json={"email": user.email})
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    resp = client.post("/api/auth/resend-verification", json={"email": user.email})
    assert resp.status_code == 429


def test_reset_password_rate_limit(client):
    for i in range(10):
        resp = client.post(
            "/api/auth/reset-password",
            json={"code": f"fake-code-{i}", "new_password": "somepassword123"},
        )
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.post(
        "/api/auth/reset-password",
        json={"code": "fake-code-final", "new_password": "somepassword123"},
    )
    assert resp.status_code == 429


def test_rate_limit_different_emails_independent(client, create_test_user):
    user_a, _ = create_test_user(email="a@example.com", is_verified=True)
    user_b, _ = create_test_user(email="b@example.com", is_verified=True)

    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user_a.email})
        assert resp.status_code == 200, f"User A request {i+1} failed"

    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user_b.email})
        assert resp.status_code == 200, f"User B request {i+1} failed"


# --- New endpoint tests ---


def test_login_rate_limit(client, verified_user):
    user, password = verified_user
    for i in range(10):
        resp = client.post("/api/auth/login", json={"email": user.email, "password": password})
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.post("/api/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 429


def test_login_global_rate_limit(client, create_test_user):
    """30 logins from same IP across different accounts should trigger global limiter."""
    users = []
    for i in range(31):
        u, pw = create_test_user(email=f"user{i}@example.com", password="pass123", is_verified=True)
        users.append((u, pw))

    for i, (u, pw) in enumerate(users[:30]):
        resp = client.post("/api/auth/login", json={"email": u.email, "password": pw})
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    u, pw = users[30]
    resp = client.post("/api/auth/login", json={"email": u.email, "password": pw})
    assert resp.status_code == 429


def test_registration_rate_limit(client):
    for i in range(5):
        resp = client.post(
            "/api/users/create",
            json={"first_name": f"User", "last_name": f"Name{i}", "email": f"reg{i}@example.com", "password": "securepass123"},
        )
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.post(
        "/api/users/create",
        json={"first_name": "User", "last_name": "Name5", "email": "reg5@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 429


def test_refresh_rate_limit(client, verified_user):
    user, password = verified_user
    login_resp = client.post("/api/auth/login", json={"email": user.email, "password": password})
    assert login_resp.status_code == 200

    for i in range(30):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 429


def test_verify_email_rate_limit(client):
    for i in range(10):
        resp = client.get(f"/api/auth/verify-email?code=fakecode{i}")
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.get("/api/auth/verify-email?code=fakecode_final")
    assert resp.status_code == 429


def test_validate_reset_code_rate_limit(client):
    for i in range(10):
        resp = client.get(f"/api/auth/reset-password?code=fakecode{i}")
        assert resp.status_code != 429, f"Request {i+1} was rate-limited unexpectedly"

    resp = client.get("/api/auth/reset-password?code=fakecode_final")
    assert resp.status_code == 429


# --- Response headers ---


def test_rate_limit_response_headers(client, verified_user):
    user, _ = verified_user
    resp = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers
    assert resp.headers["X-RateLimit-Limit"] == "5"


def test_429_includes_retry_after(client, verified_user):
    user, _ = verified_user
    for _ in range(5):
        client.post("/api/auth/forgot-password", json={"email": user.email})

    resp = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


# --- Fail-open ---


def test_fail_open_when_redis_down(client, verified_user, monkeypatch):
    """Requests should succeed when Redis is unavailable."""
    import app.core.redis as redis_module

    monkeypatch.setattr(redis_module, "_redis_client", None)

    user, _ = verified_user
    for _ in range(10):
        resp = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200


# --- Limiter independence ---


def test_limiters_are_independent(client, verified_user):
    """Exhausting forgot-password limiter should not affect reset-password limiter."""
    user, _ = verified_user
    for _ in range(5):
        client.post("/api/auth/forgot-password", json={"email": user.email})

    resp = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 429

    resp = client.post(
        "/api/auth/reset-password",
        json={"code": "fake", "new_password": "somepassword123"},
    )
    assert resp.status_code != 429
