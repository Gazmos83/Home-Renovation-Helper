"""design-import: the template download route."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.design_import import load_template
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_success_launch


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    yield c
    c.__exit__(None, None, None)


def test_the_template_downloads_as_a_json_file(client: TestClient) -> None:
    sign_in(client)
    response = client.get("/design-import/template")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert 'filename="import-template.json"' in response.headers["content-disposition"]
    body = response.json()
    assert body == load_template() and body["guide"] and body["build"]["kind"] == "custom_build"


def test_the_template_needs_the_owner_cookie(client: TestClient) -> None:
    assert client.get("/design-import/template").status_code == 401
