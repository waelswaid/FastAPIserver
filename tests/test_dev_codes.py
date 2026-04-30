import pytest

from app.core.config import settings
from app.utils import dev_codes


@pytest.fixture(autouse=True)
def reset_buffer():
    dev_codes.clear()
    yield
    dev_codes.clear()


def test_record_then_snapshot_returns_entry():
    dev_codes.record("password_reset", "user@example.com", "abc123", "https://x/?code=abc123")
    snap = dev_codes.snapshot()
    assert len(snap) == 1
    assert snap[0]["email_type"] == "password_reset"
    assert snap[0]["recipient"] == "user@example.com"
    assert snap[0]["code"] == "abc123"
    assert snap[0]["link"] == "https://x/?code=abc123"
    assert isinstance(snap[0]["captured_at"], float)


def test_snapshot_is_newest_first():
    dev_codes.record("password_reset", "a@x.com", "first", "l1")
    dev_codes.record("email_verification", "b@x.com", "second", "l2")
    dev_codes.record("invite", "c@x.com", "third", "l3")
    snap = dev_codes.snapshot()
    assert [e["code"] for e in snap] == ["third", "second", "first"]


def test_buffer_caps_at_50():
    for i in range(60):
        dev_codes.record("password_reset", f"u{i}@x.com", f"code-{i}", f"link-{i}")
    snap = dev_codes.snapshot()
    assert len(snap) == 50
    # newest first; oldest 10 dropped
    assert snap[0]["code"] == "code-59"
    assert snap[-1]["code"] == "code-10"


def test_clear_empties_buffer():
    dev_codes.record("password_reset", "user@example.com", "abc", "link")
    dev_codes.clear()
    assert dev_codes.snapshot() == []


def test_record_is_noop_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    dev_codes.record("password_reset", "user@example.com", "abc", "link")
    assert dev_codes.snapshot() == []


def test_snapshot_returns_empty_in_production_even_if_buffer_has_entries(monkeypatch):
    # Pre-populate while in dev mode
    dev_codes.record("password_reset", "user@example.com", "abc", "link")
    assert len(dev_codes.snapshot()) == 1
    # Flip to production: snapshot should report empty regardless of buffer state
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert dev_codes.snapshot() == []


def test_email_helper_populates_buffer(monkeypatch):
    """Wiring test: calling the email helper populates the dev-codes buffer."""
    # The autouse mock_send_email fixture patches send_password_reset_email at the
    # service module import sites, not at the utils module — so importing directly
    # from app.utils.email gives us the real function.
    from app.utils.email import send_password_reset_email

    monkeypatch.setattr(settings, "PASSWORD_RESET_URL", "https://example.test/reset")
    send_password_reset_email("user@example.com", "code-xyz")

    snap = dev_codes.snapshot()
    assert len(snap) == 1
    assert snap[0]["email_type"] == "password_reset"
    assert snap[0]["recipient"] == "user@example.com"
    assert snap[0]["code"] == "code-xyz"
    assert "code-xyz" in snap[0]["link"]


def test_get_codes_returns_entries(client):
    dev_codes.record("password_reset", "user@example.com", "code-1", "link-1")
    dev_codes.record("invite", "invitee@example.com", "code-2", "link-2")

    resp = client.get("/api/dev/codes")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # newest first
    assert body[0]["code"] == "code-2"
    assert body[1]["code"] == "code-1"


def test_delete_codes_clears_buffer(client):
    dev_codes.record("password_reset", "user@example.com", "code-1", "link-1")
    assert client.get("/api/dev/codes").json() != []

    resp = client.delete("/api/dev/codes")
    assert resp.status_code == 204
    assert client.get("/api/dev/codes").json() == []


def test_endpoint_returns_404_in_production(client, monkeypatch):
    """Even though the route is registered (the test app was built in dev),
    the handler-level guard ensures a 404 if ENVIRONMENT regresses to production."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    resp = client.get("/api/dev/codes")
    assert resp.status_code == 404
    resp = client.delete("/api/dev/codes")
    assert resp.status_code == 404


def test_main_does_not_register_dev_router_when_production():
    """Verifies the import-time gate in app/main.py: when ENVIRONMENT == 'production',
    the dev router is not included. We assert this by inspecting the module source
    rather than re-instantiating FastAPI in production mode (which would require
    tearing down test fixtures)."""
    import inspect
    import app.main as main_module

    src = inspect.getsource(main_module)
    # The gate must be present and must precede the dev_router include.
    assert 'if settings.ENVIRONMENT != "production":' in src
    assert "dev_router" in src
    gate_idx = src.index('if settings.ENVIRONMENT != "production":')
    include_idx = src.index("app.include_router(dev_router")
    assert gate_idx < include_idx
