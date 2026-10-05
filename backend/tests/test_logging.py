"""service-foundation: structured request and error logging."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import logging as app_logging
from app.config import Settings
from app.logging import JsonFormatter
from app.main import create_app


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def payloads(self) -> list[dict[str, object]]:
        return [json.loads(self.format(record)) for record in self.records]


@pytest.fixture
def capture() -> Iterator[Capture]:
    """Attached to the app logger directly: configure_logging() owns root."""
    handler = Capture()
    app_logging.logger.addHandler(handler)
    try:
        yield handler
    finally:
        app_logging.logger.removeHandler(handler)


def test_one_record_per_request_with_required_fields(
    settings: Settings, capture: Capture
) -> None:
    client = TestClient(create_app(settings))
    capture.records.clear()
    client.get("/health")

    requests = [p for p in capture.payloads() if p.get("message") == "request"]
    assert len(requests) == 1
    record = requests[0]
    assert record["method"] == "GET"
    assert record["path"] == "/health"
    assert record["status"] == 200
    assert isinstance(record["duration_ms"], (int, float))


def test_unhandled_error_is_logged_and_body_has_no_traceback(
    settings: Settings, capture: Capture
) -> None:
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("a very specific internal detail")

    client = TestClient(app, raise_server_exceptions=False)
    capture.records.clear()
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.text
    assert "Traceback" not in body
    assert "a very specific internal detail" not in body
    assert "RuntimeError" not in body

    errors = [p for p in capture.payloads() if p.get("error_type") == "RuntimeError"]
    assert errors, "the error type should reach the log even though not the response"
    assert any(p.get("path") == "/boom" for p in errors)


def test_json_formatter_emits_one_parseable_line() -> None:
    record = logging.LogRecord(
        name="app", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    record.context = {"method": "GET", "path": "/x", "status": 200, "duration_ms": 1.5}
    line = JsonFormatter().format(record)
    assert "\n" not in line
    parsed = json.loads(line)
    assert parsed["message"] == "hello"
    assert parsed["status"] == 200
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed
