"""service-foundation: tracing is optional, identified, and never blocking.

No network here, ever: the handler is a fake, and the only thing asserted about
Langfuse itself is that the real one is not constructed when tracing is off.
What matters is the three properties the spec names — off unless configured,
carrying owner and session, and unable to fail a turn.
"""

from __future__ import annotations

import logging
from typing import Any, Self

import pytest
from langchain_core.callbacks import BaseCallbackHandler

from app.config import Settings
from app.observability.langfuse import (
    EMAIL_MASK,
    EXPORTER_LOGGER,
    SESSION_ID_KEY,
    TAGS_KEY,
    USER_ID_KEY,
    Tracing,
    mask_personal_data,
)

OWNER = "11111111-1111-1111-1111-111111111111"
SESSION = "22222222-2222-2222-2222-222222222222"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql://u:p@localhost:5432/d",
        "openrouter_api_key": "sk-or-test",
        "cors_origins": "http://localhost:5173",
        "owner_email": "owner@example.com",
        "owner_password": "an-initial-owner-password",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


def _configured(**overrides: Any) -> Settings:
    configured: dict[str, Any] = {
        "langfuse_host": "https://cloud.langfuse.invalid",
        "langfuse_public_key": "pk-lf-test",
        "langfuse_secret_key": "sk-lf-test",
    }
    return _settings(**{**configured, **overrides})


class FakeHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self.chains = 0

    def on_chain_start(self, serialized, inputs, **kwargs):  # type: ignore[no-untyped-def]
        self.chains += 1


class FakeSpan:
    def __init__(self, client: FakeClient) -> None:
        self._client = client

    def __enter__(self) -> Self:
        self._client.open_spans += 1
        return self

    def __exit__(self, *exc: object) -> bool:
        self._client.open_spans -= 1
        self._client.closed_spans += 1
        return False


class FakeClient:
    def __init__(self, *, url: str | None = "https://langfuse.invalid/t", raises: bool = False):
        self.flushed = 0
        self.open_spans = 0
        self.closed_spans = 0
        self.ids = 0
        self.url_calls = 0
        self.opened_with: dict[str, Any] = {}
        self.updates: list[dict[str, Any]] = []
        self._url = url
        self._raises = raises

    def flush(self) -> None:
        self.flushed += 1

    def create_trace_id(self, *, seed: str | None = None) -> str:
        self.ids += 1
        return f"{self.ids:032x}"

    def start_as_current_observation(self, **kwargs: Any) -> FakeSpan:
        self.opened_with = kwargs
        return FakeSpan(self)

    def update_current_span(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def get_trace_url(self, *, trace_id: str | None = None) -> str | None:
        self.url_calls += 1
        if self._raises:
            raise ConnectionError("langfuse unreachable")
        return None if self._url is None else f"{self._url}/{trace_id}"


class BlindClient(FakeClient):
    def create_trace_id(self, *, seed: str | None = None) -> str:
        raise AttributeError("create_trace_id")


# --- off unless configured --------------------------------------------------------


def test_tracing_is_off_without_configuration() -> None:
    tracing = Tracing(_settings())
    assert tracing.enabled is False
    with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, trace_id):
        assert config is None
        assert trace_id is None


def test_an_unconfigured_deployment_never_builds_a_client() -> None:
    def explode(_settings: Settings) -> tuple[Any, Any]:
        raise AssertionError("the factory must not be called when tracing is off")

    assert Tracing(_settings(), handler_factory=explode).enabled is False


def test_tracing_is_on_when_configured() -> None:
    tracing = Tracing(_configured(), handler_factory=lambda _s: (FakeClient(), FakeHandler()))
    assert tracing.enabled is True


# --- identity -----------------------------------------------------------------------


def test_a_turns_config_carries_the_owner_and_session() -> None:
    handler = FakeHandler()
    tracing = Tracing(_configured(), handler_factory=lambda _s: (FakeClient(), handler))
    with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, _trace_id):
        pass
    assert config is not None
    assert config["callbacks"] == [handler]
    assert config["metadata"][USER_ID_KEY] == OWNER
    assert config["metadata"][SESSION_ID_KEY] == SESSION
    assert "home-renovation" in config["metadata"][TAGS_KEY]


def test_a_project_id_is_carried_when_given() -> None:
    tracing = Tracing(_configured(), handler_factory=lambda _s: (FakeClient(), FakeHandler()))
    with tracing.turn(owner_id=OWNER, session_id=SESSION, project_id="p-1") as (config, _id):
        pass
    assert config is not None
    assert config["metadata"]["langfuse_project_id"] == "p-1"


def test_the_keys_are_never_in_the_config() -> None:
    tracing = Tracing(
        _configured(langfuse_secret_key="sk-lf-c0ffee"),
        handler_factory=lambda _s: (FakeClient(), FakeHandler()),
    )
    with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, _trace_id):
        pass
    assert "c0ffee" not in repr(config)


# --- the turn's trace id --------------------------------------------------------------


def test_a_turn_yields_the_id_of_the_trace_it_opened() -> None:
    client = FakeClient()
    tracing = Tracing(_configured(), handler_factory=lambda _s: (client, FakeHandler()))
    with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, trace_id):
        assert config is not None
        assert trace_id == f"{1:032x}"
        assert client.open_spans == 1
    assert client.closed_spans == 1


def test_an_sdk_without_the_trace_api_still_answers_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracing = Tracing(_configured(), handler_factory=lambda _s: (BlindClient(), FakeHandler()))
    with caplog.at_level(logging.WARNING, logger="app"):
        with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, trace_id):
            assert config is not None
            assert trace_id is None
        with tracing.turn(owner_id=OWNER, session_id=SESSION) as (_config, second):
            assert second is None
    opened = [r for r in caplog.records if "could not open a trace" in r.message]
    assert len(opened) == 1, "reported once per process, not once per turn"
    assert opened[0].context["error_type"] == "AttributeError"


# --- never blocking -------------------------------------------------------------------


def test_a_handler_that_cannot_be_built_disables_tracing_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def explode(_settings: Settings) -> tuple[Any, Any]:
        raise RuntimeError("langfuse endpoint unreachable at construction")

    with caplog.at_level(logging.WARNING, logger="app"):
        tracing = Tracing(_configured(), handler_factory=explode)

    assert tracing.enabled is False
    with tracing.turn(owner_id=OWNER, session_id=SESSION) as (config, trace_id):
        assert (config, trace_id) == (None, None)
    records = [r for r in caplog.records if "tracing disabled" in r.message]
    assert len(records) == 1
    assert records[0].context["error_type"] == "RuntimeError"


REAL_EXPORTER = f"{EXPORTER_LOGGER}.otlp.proto.http.trace_exporter"


@pytest.fixture
def exporter_logger(caplog: pytest.LogCaptureFixture) -> Any:
    root = logging.getLogger()
    before = {h: list(h.filters) for h in root.handlers}
    yield logging.getLogger(REAL_EXPORTER)
    for handler in root.handlers:
        for f in list(handler.filters):
            if f not in before.get(handler, []):
                handler.removeFilter(f)


def test_an_unreachable_collector_is_reported_once_however_often_it_retries(
    caplog: pytest.LogCaptureFixture, exporter_logger: Any
) -> None:
    with caplog.at_level(logging.WARNING):
        tracing = Tracing(_configured(), handler_factory=lambda _s: (FakeClient(), FakeHandler()))
        caplog.handler.addFilter(tracing._export_filter)
        for attempt in range(5):
            exporter_logger.warning("Transient error ... retrying in %ss", attempt)
        exporter_logger.error("Failed to export span batch.")

    ours = [r for r in caplog.records if "tracing export failed" in r.message]
    assert len(ours) == 1
    assert ours[0].context["exporter"] == REAL_EXPORTER
    assert not [r for r in caplog.records if r.name.startswith(EXPORTER_LOGGER)]


def test_a_failing_flush_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    class BadClient:
        def flush(self) -> None:
            raise RuntimeError("cannot reach langfuse")

    tracing = Tracing(_configured(), handler_factory=lambda _s: (BadClient(), FakeHandler()))
    with caplog.at_level(logging.WARNING, logger="app"):
        tracing.flush()
    assert [r for r in caplog.records if "could not be flushed" in r.message]


def test_flushing_when_tracing_is_off_is_a_no_op() -> None:
    Tracing(_settings()).flush()


# --- output and masking ---------------------------------------------------------------


def test_the_turns_reply_or_failure_becomes_the_output() -> None:
    class Result:
        def __init__(self, reply: str | None, failure_class: str | None) -> None:
            self.reply, self.failure_class = reply, failure_class

    client = FakeClient()
    tracing = Tracing(_configured(), handler_factory=lambda _s: (client, FakeHandler()))
    with tracing.turn(owner_id=OWNER, session_id=SESSION):
        tracing.record_output(Result("The answer.", None))
        tracing.record_output(Result(None, "timeout"))
        tracing.record_output(Result(None, None))
    assert client.updates == [{"output": "The answer."}, {"output": {"failure_class": "timeout"}}]


def test_email_addresses_are_masked_everywhere_in_exported_data() -> None:
    data = {
        "input": "Write to anna.meier@example.de about it",
        "messages": [{"content": "cc ben@studio.example.com"}, ("tuple", "x@y.io")],
        "tokens": 12,
    }
    masked = mask_personal_data(data=data)
    assert masked == {
        "input": f"Write to {EMAIL_MASK} about it",
        "messages": [{"content": f"cc {EMAIL_MASK}"}, ("tuple", EMAIL_MASK)],
        "tokens": 12,
    }
    assert mask_personal_data(data="18 mm birch plywood") == "18 mm birch plywood"


def test_a_langchain_message_is_masked_too() -> None:
    from langchain_core.messages import AIMessage

    masked = mask_personal_data(
        data={"messages": [AIMessage(content="Nothing sent to anna@example.de.")]}
    )
    assert "anna@example.de" not in repr(masked)
    assert masked["messages"][0]["content"] == f"Nothing sent to {EMAIL_MASK}."
