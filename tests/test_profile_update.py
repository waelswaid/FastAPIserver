# Update first_name returns 200 with updated data
def test_update_first_name_success(auth_client):
    client, access_token, user = auth_client
    resp = client.patch(
        "/api/users/me",
        json={"first_name": "Updated"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Updated"


# Update last_name returns 200 with updated data
def test_update_last_name_success(auth_client):
    client, access_token, user = auth_client
    resp = client.patch(
        "/api/users/me",
        json={"last_name": "NewLast"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["last_name"] == "NewLast"


# GET /users/me reflects the updated first_name
def test_update_first_name_persists(auth_client):
    client, access_token, user = auth_client
    client.patch(
        "/api/users/me",
        json={"first_name": "Persisted"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Persisted"


# Null first_name field leaves first_name unchanged
def test_update_null_first_name_no_change(auth_client):
    client, access_token, user = auth_client
    original_first_name = user.first_name
    resp = client.patch(
        "/api/users/me",
        json={"first_name": None},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == original_first_name


# Empty body leaves profile unchanged
def test_update_empty_body(auth_client):
    client, access_token, user = auth_client
    original_first_name = user.first_name
    original_last_name = user.last_name
    resp = client.patch(
        "/api/users/me",
        json={},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == original_first_name
    assert resp.json()["last_name"] == original_last_name


# Empty string first_name is rejected (min_length=1)
def test_update_empty_string_first_name_rejected(auth_client):
    client, access_token, user = auth_client
    resp = client.patch(
        "/api/users/me",
        json={"first_name": ""},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 422


# Empty string last_name is rejected (min_length=1)
def test_update_empty_string_last_name_rejected(auth_client):
    client, access_token, user = auth_client
    resp = client.patch(
        "/api/users/me",
        json={"last_name": ""},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 422


# Unauthenticated request returns 401
def test_update_profile_unauthenticated(client):
    resp = client.patch("/api/users/me", json={"first_name": "Hacker"})
    assert resp.status_code == 401
