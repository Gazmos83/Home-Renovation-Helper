"""One real turn chain in the pinned Blender, driven by scripted models.

brief → `create_piece` builds the fold-down desk for real → the Builder renders a
`draft` turntable (tier `draft`: 12 frames, 600 × 600, Eevee).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.blender import storage
from app.render import benchmark_store
from tests.api_helpers import desk, make_client, sign_in
from tests.blender_fakes import png_size
from tests.conftest import clean_house_file, wait_for_status
from tests.fakes import tool_call
from tests.graph_helpers import fake_models
from tests.test_chat_api import HALL, install, start

pytestmark = pytest.mark.blender


@pytest.fixture
def client(migrated_database: str, render_root: Path, blender_bin: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, blender_bin, None)  # the real launcher
    clean_house_file(c.app.state.engine)
    sign_in(c)
    # The estimate needs a benchmark; a stored figure stands in for running one.
    benchmark_store.write_benchmark(c.app.state.engine, 6.0, blender_version="5.2.1 LTS")
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def test_a_chat_builds_the_desk_and_renders_a_draft_turntable(client: TestClient, render_root: Path) -> None:
    install(client, fake_models(
        foreman={"decisions": [
            {"specialist": "intake", "reason": "t"},
            {"specialist": "designer", "reason": "t"},
            {"specialist": "builder", "reason": "t"},
            {"specialist": "builder", "reason": "t"},
        ]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
        designer={"steps": [[tool_call("create_piece", {"package_id": "hall-desk", "spec": desk()})], "Created."]},
        builder={"steps": [
            [tool_call("blender_build", {"package_id": "hall-desk"})],
            "Built.",
            [tool_call("render_turntable", {"package_id": "hall-desk", "tier": "draft"})],
            "A draft turntable has started.",
        ]},
    ))
    thread = start(client)

    def confirm(paused: dict) -> dict:
        response = client.post(
            f"/chat/threads/{thread}/resume",
            json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
        )
        assert response.status_code == 200, response.text
        return response.json()

    confirm(client.post(f"/chat/threads/{thread}/turns", json={"message": "a fold-down desk"}).json())
    created = confirm(client.post(f"/chat/threads/{thread}/turns", json={"message": "design it"}).json())
    assert created["reply"] == "Created."

    built = client.post(f"/chat/threads/{thread}/turns", json={"message": "build it"})
    assert built.status_code == 200, built.text
    folder = storage.version_dir(render_root, "hall-desk", 1)
    assert wait_for_status(folder, seconds=120)["status"] == "succeeded"
    assert png_size(folder / "screenshot.png") == (800, 500)

    rendered = client.post(f"/chat/threads/{thread}/turns", json={"message": "a draft turntable"})
    assert rendered.status_code == 200, rendered.text
    deadline = time.monotonic() + 240
    job: dict = {}
    while time.monotonic() < deadline:
        job = (storage.read_status(folder) or {}).get("renders", {}).get("turntable") or {}
        if job.get("status") in ("succeeded", "failed"):
            break
        time.sleep(1)
    assert job.get("status") == "succeeded", job
    assert job["tier"] == "draft"
    frames = sorted((folder / "frames").glob("frame_*.png"))
    assert len(frames) == 12
    assert png_size(frames[0]) == (600, 600)
