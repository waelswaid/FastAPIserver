# 6th forgot-password request for the same email returns 429 (limit is 5/hour)
def test_forgot_password_rate_limit(client, verified_user):
    user, _ = verified_user
    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    resp = client.post("/api/auth/forgot-password", json={"email": user.email})
    assert resp.status_code == 429


# 6th resend-verification request for the same email returns 429 (limit is 5/hour)
def test_resend_verification_rate_limit(client, unverified_user):
    user, _ = unverified_user
    for i in range(5):
        resp = client.post("/api/auth/resend-verification", json={"email": user.email})
        assert resp.status_code == 200, f"Request {i+1} failed unexpectedly"

    resp = client.post("/api/auth/resend-verification", json={"email": user.email})
    assert resp.status_code == 429


# 11th reset-password request from the same IP returns 429 (limit is 10/hour)
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


# Different emails have independent rate limit counters
def test_rate_limit_different_emails_independent(client, create_test_user):
    user_a, _ = create_test_user(email="a@example.com", is_verified=True)
    user_b, _ = create_test_user(email="b@example.com", is_verified=True)

    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user_a.email})
        assert resp.status_code == 200, f"User A request {i+1} failed"

    for i in range(5):
        resp = client.post("/api/auth/forgot-password", json={"email": user_b.email})
        assert resp.status_code == 200, f"User B request {i+1} failed"
