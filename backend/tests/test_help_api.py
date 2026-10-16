"""help-center: the owner-gated help route."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_success_launch


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    yield c
    c.__exit__(None, None, None)


def test_the_owner_reads_the_help_topics_in_order(client: TestClient) -> None:
    sign_in(client)
    response = client.get("/help")
    assert response.status_code == 200
    topics = response.json()["topics"]
    assert [topic["id"] for topic in topics] == ["blueprint", "files", "template", "renders", "conversations", "workflow"]
    template = next(topic for topic in topics if topic["id"] == "template")
    assert template["download"] == "import_template" and "JSON alone" in template["prompt"]


def test_the_help_holds_no_model_token_or_cost(client: TestClient) -> None:
    sign_in(client)
    text = json.dumps(client.get("/help").json()).lower()
    for word in ("openrouter", "deepseek", "openai/", "token", "cost"):
        assert word not in text


def test_the_help_needs_the_owner_cookie(client: TestClient) -> None:
    assert client.get("/help").status_code == 401
