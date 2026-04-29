"""Tests for the dev-mode console branch in app/utils/email.py.

When ENVIRONMENT != "production", the three send_* functions log a
single audit-style line and skip the Mailgun HTTP call. ENVIRONMENT
is already set to "development" by conftest.py, so the dev branch
should fire by default in tests that exercise the real send_* code.
"""
import logging
from unittest.mock import patch, MagicMock

import pytest

from app.core.config import settings
from app.utils.email import (
    send_verification_email,
    send_password_reset_email,
    send_invite_email,
)


@pytest.fixture
def mock_send_email():
    """Override the conftest autouse fixture so the real send_* runs.

    The conftest version patches the service-module imports of these
    functions; here we want to call the real implementations directly.
    """
    yield None


def test_dev_console_logs_verification_email(caplog):
    with patch("app.utils.email.requests.post") as mock_post:
        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            send_verification_email("user@example.com", "abc-123")

    assert not mock_post.called, "Mailgun HTTP call should be skipped in dev mode"
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "event=dev_email" in messages
    assert "type=email_verification" in messages
    assert "recipient=user@example.com" in messages
    assert "code=abc-123" in messages
    assert "link=http://localhost:8000/api/auth/verify-email?code=abc-123" in messages


def test_dev_console_logs_password_reset_email(caplog):
    with patch("app.utils.email.requests.post") as mock_post:
        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            send_password_reset_email("user@example.com", "reset-456")

    assert not mock_post.called, "Mailgun HTTP call should be skipped in dev mode"
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "event=dev_email" in messages
    assert "type=password_reset" in messages
    assert "recipient=user@example.com" in messages
    assert "code=reset-456" in messages
    assert "link=http://localhost:8000/api/auth/reset-password?code=reset-456" in messages


def test_dev_console_logs_invite_email(caplog):
    with patch("app.utils.email.requests.post") as mock_post:
        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            send_invite_email("user@example.com", "inv-789")

    assert not mock_post.called, "Mailgun HTTP call should be skipped in dev mode"
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "event=dev_email" in messages
    assert "type=invite" in messages
    assert "recipient=user@example.com" in messages
    assert "code=inv-789" in messages
    assert "link=http://localhost:8000/api/auth/accept-invite?code=inv-789" in messages


def test_production_environment_skips_dev_console(monkeypatch, caplog):
    """In production, the Mailgun call must run and the dev_email line must NOT be emitted."""
    # One representative function is enough — all three share _is_dev_mode().
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with patch("app.utils.email.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            send_verification_email("user@example.com", "abc-123")

    assert mock_post.called, "Mailgun HTTP call should run in production"
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "event=dev_email" not in messages
