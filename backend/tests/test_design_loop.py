"""design-agents: the whole loop against fake models.

wish → `record_brief` yes → `create_piece` yes → `blender_build` → a `draft`
turntable (tier `draft`) → "three shelves" → `revise_package` yes → version 2.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.agent import chat, house_file
from app.blender import storage
from app.db.models import ModelUsage, User
from tests.api_helpers import desk
from tests.conftest import wait_for_status
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a fold-down desk by the front door",
    "style": "light oak",
    "budget_eur": 400,
}


@pytest.fixture
def owner(tool_state):
    with Session(tool_state.engine) as session:
        user = User(email=f"loop-{uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(user)
        session.commit()
        user_id = user.id
    yield user_id
    with Session(tool_state.engine) as session:
        session.execute(text("DELETE FROM model_usage WHERE user_id = :u"), {"u": user_id})
        session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        session.commit()


def pieces(tool_state) -> dict:
    with Session(tool_state.engine) as session:
        return {p["package_id"]: p for p in house_file.pieces(session, tool_state.settings.render_root)}


def test_the_full_loop(tool_state, owner) -> None:
    root = tool_state.settings.render_root
    shelves = desk()["modules"][0]["shelves"]
    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "intake", "reason": "a wish"},
                {"specialist": "designer", "reason": "numbers confirmed"},
                {"specialist": "builder", "reason": "build it"},
                {"specialist": "builder", "reason": "render it"},
                {"specialist": "designer", "reason": "a change"},
            ]
        },
        intake={"steps": [[tool_call("record_brief", HALL)], "Numbers saved. Shall I design it?"]},
        designer={
            "steps": [
                [tool_call("create_piece", {"package_id": "hall-desk", "spec": desk()})],
                "The desk is created and building.",
                [tool_call("revise_package", {
                    "package_id": "hall-desk",
                    "changes": {"modules": {"cabinet": {"shelves": shelves + 1}}},
                })],
                "Version 2 is created.",
            ]
        },
        builder={
            "steps": [
                [tool_call("blender_build", {"package_id": "hall-desk"})],
                "Built; the screenshot is at the route above.",
                [tool_call("render_turntable", {"package_id": "hall-desk", "tier": "draft"})],
                "A draft turntable has started.",
            ]
        },
    )
    harness = make_harness(tool_state, models)
    harness.owner_id = owner
    thread, who = harness.thread, owner

    # 1. wish → record_brief → yes
    paused = chat.answer(harness.graph, thread_id=thread, owner_id=who, message="a fold-down desk for the hall, 400 euro")
    assert (paused.specialist, paused.pending.subject) == ("intake", "brief")
    with Session(tool_state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is None
    done = chat.resume(harness.graph, thread_id=thread, owner_id=who, answer_value="yes")
    assert done.reply == "Numbers saved. Shall I design it?"
    with Session(tool_state.engine) as session:
        assert house_file.room_by_name(session, "Hall").height_mm == 2400
        assert house_file.preferences(session) == {"style": "light oak", "budget_eur": "400"}
    assert pieces(tool_state) == {}

    # 2. create_piece → yes
    paused = chat.answer(harness.graph, thread_id=thread, owner_id=who, message="design it")
    assert (paused.specialist, paused.pending.subject) == ("designer", "create_piece")
    assert storage.versions(root, "hall-desk") == []
    done = chat.resume(harness.graph, thread_id=thread, owner_id=who, answer_value="yes")
    assert done.reply == "The desk is created and building."
    assert storage.versions(root, "hall-desk") == [1]
    piece = pieces(tool_state)["hall-desk"]
    assert piece["brief"]["budget_eur"] == 400 and piece["room_id"] is not None
    assert [v["version"] for v in piece["versions"]] == [1]

    # 3. the Builder builds and reports
    built = chat.answer(harness.graph, thread_id=thread, owner_id=who, message="build it")
    assert built.specialist == "builder" and built.pending is None
    assert wait_for_status(storage.version_dir(root, "hall-desk", 1))["status"] == "succeeded"
    assert (storage.version_dir(root, "hall-desk", 1) / "screenshot.png").is_file()

    # 4. a draft turntable: no pause, tier draft, 12 frames at 600 px
    rendered = chat.answer(harness.graph, thread_id=thread, owner_id=who, message="a draft turntable please")
    assert rendered.specialist == "builder" and rendered.pending is None
    import time

    deadline = time.monotonic() + 10
    folder1 = storage.version_dir(root, "hall-desk", 1)
    while time.monotonic() < deadline:
        job = (storage.read_status(folder1) or {}).get("renders", {}).get("turntable") or {}
        if job.get("status") == "succeeded":
            break
        time.sleep(0.05)
    assert job["tier"] == "draft"
    assert len(list((folder1 / "frames").glob("frame_*.png"))) == 12

    # 5. "three shelves" → revise_package → yes → version 2, version 1 untouched
    v1_input = (folder1 / "input.json").read_text(encoding="utf-8")
    paused = chat.answer(harness.graph, thread_id=thread, owner_id=who, message=f"make it {shelves + 1} shelves in the cabinet")
    assert (paused.specialist, paused.pending.subject) == ("designer", "revise")
    assert f"cabinet: shelves {shelves} → {shelves + 1}" in paused.pending.summary
    assert storage.versions(root, "hall-desk") == [1]
    done = chat.resume(harness.graph, thread_id=thread, owner_id=who, answer_value="yes")
    assert done.reply == "Version 2 is created."
    assert storage.versions(root, "hall-desk") == [1, 2]
    assert (folder1 / "input.json").read_text(encoding="utf-8") == v1_input
    wait_for_status(storage.version_dir(root, "hall-desk", 2))
    second = pieces(tool_state)["hall-desk"]["versions"][1]
    assert (second["version"], second["revised_from"]) == (2, 1)
    assert second["changes"] == [f"cabinet: shelves {shelves} → {shelves + 1}"]

    # Usage: one row per model call, each naming its slot's model.
    with Session(tool_state.engine) as session:
        rows = session.scalars(select(ModelUsage).where(ModelUsage.user_id == owner)).all()
    by_model: dict[str, int] = {}
    for row in rows:
        by_model[row.model_id] = by_model.get(row.model_id, 0) + 1
    assert by_model == {
        "fake/foreman": 5,
        "fake/intake": 2,
        "fake/designer": 4,
        "fake/builder": 4,
    }
    assert {row.operation for row in rows} == {"chat.foreman", "chat.intake", "chat.designer", "chat.builder"}
