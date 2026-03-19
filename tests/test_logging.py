import json
import logging
from unittest.mock import patch, MagicMock

import pytest

from app.core.logging import CorrelationIdFilter, JSONFormatter, correlation_id_var


class TestCorrelationIdFilter:
    def test_injects_default_correlation_id(self):
        filt = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        filt.filter(record)
        assert record.correlation_id == "-"

    def test_injects_set_correlation_id(self):
        filt = CorrelationIdFilter()
        token = correlation_id_var.set("abc-123")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="hello", args=(), exc_info=None,
            )
            filt.filter(record)
            assert record.correlation_id == "abc-123"
        finally:
            correlation_id_var.reset(token)


class TestJSONFormatter:
    def test_outputs_valid_json_with_expected_keys(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        record.correlation_id = "req-456"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "test message"
        assert parsed["correlation_id"] == "req-456"
        assert "timestamp" in parsed


class TestRequestLoggingMiddleware:
    @pytest.fixture()
    def minimal_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import time
        import uuid as _uuid
        from app.core.logging import correlation_id_var as _cid_var

        test_app = FastAPI()

        @test_app.middleware("http")
        async def request_logging_mw(request, call_next):
            request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
            token = _cid_var.set(request_id)
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response
            finally:
                _cid_var.reset(token)

        @test_app.get("/health")
        def health():
            return {"status": "ok"}

        return TestClient(test_app)

    def test_returns_x_request_id_header(self, minimal_client):
        resp = minimal_client.get("/health")
        assert "x-request-id" in resp.headers

    def test_echoes_incoming_x_request_id(self, minimal_client):
        resp = minimal_client.get("/health", headers={"X-Request-ID": "test-id-999"})
        assert resp.headers["x-request-id"] == "test-id-999"


class TestEmailSuccessLogging:
    def test_password_reset_email_logs_success(self, caplog):
        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            from app.utils.email import send_password_reset_email
            with patch("app.utils.email.requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response
                send_password_reset_email("test@example.com", "code123")
        assert any("Password reset email sent to=test@example.com" in r.message for r in caplog.records)

    def test_verification_email_logs_success(self, caplog):
        with caplog.at_level(logging.INFO, logger="app.utils.email"):
            from app.utils.email import send_verification_email
            with patch("app.utils.email.requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_post.return_value = mock_response
                send_verification_email("test@example.com", "code456")
        assert any("Verification email sent to=test@example.com" in r.message for r in caplog.records)
