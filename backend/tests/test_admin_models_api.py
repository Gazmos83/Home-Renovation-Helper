"""dev-panel: routing, generation and budget routes, probe-before-switch, live swap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import ConfigurationError, Settings
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.api_helpers import reset_owner, sign_in
from tests.blender_fakes import fake_pipeline_launch

HAIKU = "anthropic/claude-haiku-4.5"
DESIGNER_DEFAULT = "deepseek/deepseek-v4-pro-0813"


def _client(database_url: str, render_root: Path, binary: Path, *, dev: bool) -> TestClient:
    settings = Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        dev_panel_enabled=dev,
        render_root=render_root,
        blender_bin=binary,
        _env_file=None,
    )
    reset_owner(database_url)
    engine = make_engine(database_url)
    with Session(engine) as session:
        session.execute(
            text(
                "DELETE FROM operator_settings WHERE key LIKE 'routing:%' "
                "OR key LIKE 'budget:%' OR key LIKE 'generation:%' OR key LIKE 'plugin:%'"
            )
        )
        session.commit()
    engine.dispose()
    app = create_app(settings)
    app.state.blender_launch = fake_pipeline_launch()
    client = TestClient(app)
    client.__enter__()
    return client


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> TestClient:
    app_client = _client(migrated_database, render_root, fake_blender, dev=True)
    sign_in(app_client)
    yield app_client
    app_client.__exit__(None, None, None)


def test_panel_disabled_answers_404(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    client = _client(migrated_database, render_root, fake_blender, dev=False)
    sign_in(client)
    try:
        assert client.get("/admin/models").status_code == 404
        assert client.put("/admin/routing/designer", json={"model": HAIKU}).status_code == 404
    finally:
        client.__exit__(None, None, None)


def test_a_probed_switch_applies_to_the_next_call(client: TestClient) -> None:
    with patch("app.api.admin_models.probe_slug") as probe:
        response = client.put("/admin/routing/designer", json={"model": HAIKU})
    assert response.status_code == 200
    probe.assert_called_once()
    assert response.json()["model"] == HAIKU
    listed = client.get("/admin/models").json()
    designer = next(row for row in listed["slots"] if row["slot"] == "designer")
    assert designer["model"] == HAIKU
    assert designer["override"] is True
    assert client.app.state.routing.model_for("designer") == HAIKU


def test_a_failed_probe_leaves_routing_unchanged(client: TestClient) -> None:
    with patch(
        "app.api.admin_models.probe_slug",
        side_effect=ConfigurationError(f"model {HAIKU} blocked by gateway: guardrail"),
    ):
        response = client.put("/admin/routing/designer", json={"model": HAIKU})
    assert response.status_code == 422
    assert HAIKU in response.json()["detail"]["reason"]
    assert client.app.state.routing.model_for("designer") == DESIGNER_DEFAULT


def test_reset_restores_the_file(client: TestClient) -> None:
    with patch("app.api.admin_models.probe_slug"):
        client.put("/admin/routing/designer", json={"model": HAIKU})
    response = client.delete("/admin/routing/designer")
    assert response.status_code == 200
    assert response.json()["model"] == DESIGNER_DEFAULT
    assert response.json()["override"] is False


def test_an_out_of_range_value_is_refused_naming_the_field(client: TestClient) -> None:
    response = client.put(
        f"/admin/models/{DESIGNER_DEFAULT}/generation",
        json={"temperature": 9, "max_output_tokens": 16},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "temperature"


def test_a_lowered_ceiling_is_stored(client: TestClient) -> None:
    response = client.put(
        f"/admin/models/{DESIGNER_DEFAULT}/budget",
        json={"context_budget_tokens": 8000, "daily_token_ceiling": 10},
    )
    assert response.status_code == 200
    assert response.json()["daily_token_ceiling"] == 10
    listed = client.get("/admin/models").json()
    model = next(row for row in listed["models"] if row["slug"] == DESIGNER_DEFAULT)
    assert model["daily_token_ceiling"] == 10
    assert model["context_budget_tokens"] == 8000
