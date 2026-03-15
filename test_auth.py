import requests

# end-to-end test script
BASE_URL = "http://127.0.0.1:8000/api"

TEST_USER = {
    "name": "Test User1",
    "email": "testuser1@example.com",
    "password": "securepassword123",
}


def test_register(session):
    print("\n--- Test: Register user ---")
    r = session.post(f"{BASE_URL}/users/create", json=TEST_USER)
    if r.status_code == 200:
        print(f"PASS — user created: {r.json()['email']}")
    elif r.status_code == 409:
        print("INFO — user already exists, continuing with tests")
    else:
        print(f"FAIL — unexpected status {r.status_code}: {r.json()}")


def test_login_valid(session):
    print("\n--- Test: Login with correct credentials ---")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_USER["email"],
        "password": TEST_USER["password"],
    })
    if r.status_code == 200:
        token = r.json().get("access_token")
        has_cookie = "refresh_token" in session.cookies
        print(f"PASS — access token received")
        print(f"  access_token (first 40 chars): {token[:40]}...")
        print(f"  refresh_token cookie set: {has_cookie}")
        return token
    else:
        print(f"FAIL — status {r.status_code}: {r.json()}")
        return None


def test_login_wrong_password(session):
    print("\n--- Test: Login with wrong password ---")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_USER["email"],
        "password": "wrongpassword999",
    })
    if r.status_code == 401:
        print(f"PASS — correctly rejected: {r.json()['detail']}")
    else:
        print(f"FAIL — expected 401, got {r.status_code}: {r.json()}")


def test_login_nonexistent_email(session):
    print("\n--- Test: Login with non-existent email ---")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": "nobody@example.com",
        "password": "somepassword123",
    })
    if r.status_code == 401:
        print(f"PASS — correctly rejected: {r.json()['detail']}")
    else:
        print(f"FAIL — expected 401, got {r.status_code}: {r.json()}")


def test_get_me(session, token):
    print("\n--- Test: GET /users/me with valid token ---")
    r = session.get(f"{BASE_URL}/users/me", headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 200:
        data = r.json()
        print(f"PASS — returned user: {data['email']}")
    else:
        print(f"FAIL — status {r.status_code}: {r.json()}")


def test_get_me_no_token(session):
    print("\n--- Test: GET /users/me without token ---")
    r = session.get(f"{BASE_URL}/users/me")
    if r.status_code == 401:
        print(f"PASS — correctly rejected with 401")
    else:
        print(f"FAIL — expected 401, got {r.status_code}: {r.json()}")


def test_refresh(session):
    print("\n--- Test: POST /auth/refresh using cookie ---")
    r = session.post(f"{BASE_URL}/auth/refresh")
    if r.status_code == 200:
        new_token = r.json().get("access_token")
        print(f"PASS — new access token received")
        print(f"  access_token (first 40 chars): {new_token[:40]}...")
        return new_token
    else:
        print(f"FAIL — status {r.status_code}: {r.json()}")
        return None


def test_logout(session, token):
    print("\n--- Test: POST /auth/logout ---")
    r = session.post(f"{BASE_URL}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 204:
        has_cookie = "refresh_token" in session.cookies
        print(f"PASS — logged out successfully")
        print(f"  refresh_token cookie cleared: {not has_cookie}")
    else:
        print(f"FAIL — status {r.status_code}: {r.text}")


def test_get_me_after_logout(session, token):
    print("\n--- Test: GET /users/me with blacklisted token ---")
    r = session.get(f"{BASE_URL}/users/me", headers={"Authorization": f"Bearer {token}"})
    if r.status_code == 401:
        print(f"PASS — blacklisted token correctly rejected")
    else:
        print(f"FAIL — expected 401, got {r.status_code}: {r.json()}")


def test_refresh_after_logout(session):
    print("\n--- Test: POST /auth/refresh after cookie cleared ---")
    r = session.post(f"{BASE_URL}/auth/refresh")
    if r.status_code == 401:
        print(f"PASS — refresh correctly rejected with no cookie")
    else:
        print(f"FAIL — expected 401, got {r.status_code}: {r.json()}")


if __name__ == "__main__":
    session = requests.Session()

    test_register(session)
    test_login_wrong_password(session)
    test_login_nonexistent_email(session)

    token = test_login_valid(session)
    if token:
        test_get_me(session, token)
        test_get_me_no_token(session)
        new_token = test_refresh(session)
        if new_token:
            test_logout(session, new_token)
            test_get_me_after_logout(session, new_token)
            test_refresh_after_logout(session)

    print("\nDone.")
