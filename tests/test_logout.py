# Logout returns 204 and the old access token is rejected on /users/me
def test_logout_success(auth_client):
    client, access_token, user = auth_client

    resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    me_resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 401


# Logout without a refresh cookie still succeeds (204)
def test_logout_no_refresh_cookie(client, verified_user):
    user, password = verified_user
    login_resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    access_token = login_resp.json()["access_token"]

    client.cookies.clear()
    resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204


# Invalid access token on logout returns 401
def test_logout_invalid_access_token(client):
    resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


# Logout blacklists the refresh token too — refresh fails after logout
def test_logout_refresh_token_also_blacklisted(auth_client):
    client, access_token, user = auth_client

    resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 204

    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 401
