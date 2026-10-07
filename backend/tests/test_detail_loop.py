"""Lighting & materials end to end with fake models and a fake socket (photoreal-detail)."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from app.agent.foreman import last_reply
from app.agent.tools.create_piece import run as create_run
from app.blender import storage
from tests.api_helpers import desk
from tests.conftest import wait_for_status
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.live_helpers import FakeBlender
from tests.test_builder_tools import wait_job


def digest(folder, name: str) -> str:
    return hashlib.sha256((folder / name).read_bytes()).hexdigest()


def test_a_detail_pass_to_an_approved_final_never_touches_the_spec(tool_state, make_ctx) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    folder = storage.version_dir(tool_state.settings.render_root, "bench", 1)
    wait_for_status(folder)
    before = {name: digest(folder, name) for name in ("model.blend", "spec.json", "cutlist.csv")}
    tool_state.live_blender = live = FakeBlender()

    models = fake_models(
        foreman={"decisions": [{"specialist": "lighting", "reason": "detail"}]},
        lighting={
            "steps": [
                [tool_call("start_detail_pass", {}, "c1")],
                [tool_call("run_detail_script", {"code": "# AGENT\nimport bpy\n", "purpose": "oak"}, "c2")],
                [tool_call("detail_screenshot", {}, "c3")],
                [tool_call("render_detail", {"tier": "final", "kind": "still"}, "c4")],
                "The final still is rendering.",
            ]
        },
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")

    harness.turn("make the oak realistic and give me a final image")
    [pause] = harness.snapshot().interrupts
    assert pause.value["subject"] == "detail_pass"
    assert live.scripts == []

    harness.answer("yes")
    [pause] = harness.snapshot().interrupts
    assert pause.value["subject"] == "detail_render"
    assert pause.value["proposal"]["tier"] == "final"
    assert not any("render_still.py" in part for call in tool_state.launched for part in call)

    state = harness.answer("yes")
    assert last_reply(state) == "The final still is rendering."
    wait_job(folder, "detail-still")
    renders = [c for c in tool_state.launched if any(p.endswith("render_still.py") for p in c)]
    assert len(renders) == 1 and renders[0][renders[0].index("--tier-engine") + 1] == "CYCLES"

    # The agent saw the scene as text, and no image reached its model.
    text = models["lighting"].last_prompt_text()
    assert "objects: 2" in text and "cannot see images" in text
    assert all(isinstance(m.content, str) for prompt in models["lighting"].prompts for m in prompt)
    assert (storage.detail_dir(folder) / "screens" / "screen_000.png").is_file()
    assert (storage.detail_dir(folder) / "still.png").is_file()

    # Step 3 wrote nothing back: the spec, the cut list and the model are as built.
    assert {name: digest(folder, name) for name in before} == before
    assert storage.versions(tool_state.settings.render_root, "bench") == [1]


def test_declining_the_pass_leaves_the_live_blender_alone(tool_state, make_ctx) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    folder = storage.version_dir(tool_state.settings.render_root, "bench", 1)
    wait_for_status(folder)
    tool_state.live_blender = live = FakeBlender()
    models = fake_models(
        foreman={"decisions": [{"specialist": "lighting", "reason": "detail"}]},
        lighting={"steps": [[tool_call("start_detail_pass", {}, "c1")], "Understood, nothing was started."]},
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("detail it")
    state = harness.answer("no")
    assert "The detail pass was not started." in str(state["messages"][-2].content)
    assert live.scripts == []
    assert not storage.detail_dir(folder).exists()
