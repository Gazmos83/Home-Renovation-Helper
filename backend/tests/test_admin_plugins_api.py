"""dev-panel: plugin list, global enable/disable, invocations."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import sign_in
from tests.test_admin_models_api import _client


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> TestClient:
    app_client = _client(migrated_database, render_root, fake_blender, dev=True)
    sign_in(app_client)
    yield app_client
    app_client.__exit__(None, None, None)


def test_plugins_are_listed_with_kind_role_and_tools(client: TestClient) -> None:
    response = client.get("/admin/plugins")
    assert response.status_code == 200
    by_name = {row["name"]: row for row in response.json()}
    assert by_name["room_fit"]["kind"] == "builtin"
    assert by_name["room_fit"]["role"] == "designer"
    assert by_name["room_fit"]["tools"] == ["room_fit"]
    assert by_name["room_fit"]["enabled"] is True
    assert by_name["intake"]["toggleable"] is False


def test_a_plugin_can_be_disabled_globally(client: TestClient) -> None:
    response = client.put("/admin/plugins/room_fit", json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    listed = {row["name"]: row for row in client.get("/admin/plugins").json()}
    assert listed["room_fit"]["enabled"] is False
    client.put("/admin/plugins/room_fit", json={"enabled": True})


def test_invocations_return_outcome_and_duration_only(client: TestClient) -> None:
    response = client.get("/admin/plugins/room_fit/invocations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    for row in response.json():
        assert set(row) <= {"outcome", "duration_ms", "created_at"}


def test_unknown_plugin_is_404(client: TestClient) -> None:
    assert client.put("/admin/plugins/nope", json={"enabled": False}).status_code == 404
