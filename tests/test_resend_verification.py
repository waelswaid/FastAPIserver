import requests


# Unverified user gets 200 and verification email is sent
def test_resend_success(client, unverified_user, mock_send_email):
    user, _ = unverified_user
    resp = client.post(
        "/api/auth/resend-verification",
        json={"email": user.email},
    )
    assert resp.status_code == 200
    mock_send_email.assert_called_once()


# Already-verified user gets 200 but no email is sent
def test_resend_already_verified(client, verified_user, mock_send_email):
    user, _ = verified_user
    resp = client.post(
        "/api/auth/resend-verification",
        json={"email": user.email},
    )
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


# Non-existent email gets 200 but no email is sent (no info leakage)
def test_resend_nonexistent_email(client, mock_send_email):
    resp = client.post(
        "/api/auth/resend-verification",
        json={"email": "nobody@example.com"},
    )
    assert resp.status_code == 200
    mock_send_email.assert_not_called()


# Mailgun failure returns 503
def test_resend_email_failure(client, unverified_user, mock_send_email):
    user, _ = unverified_user
    mock_send_email.return_value.raise_for_status.side_effect = requests.RequestException("fail")
    resp = client.post(
        "/api/auth/resend-verification",
        json={"email": user.email},
    )
    assert resp.status_code == 503
