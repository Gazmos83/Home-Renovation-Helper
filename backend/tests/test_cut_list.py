"""design-agents: `cut_list` derives parts and hardware with no process."""

from __future__ import annotations

from dataclasses import replace

from app.agent.tools.create_piece import run as create_run
from app.agent.tools.cut_list import run
from app.blender import storage
from app.blender.custom_build import derive as custom_derive
from tests.api_helpers import desk
from tests.conftest import wait_for_status


def test_it_lists_the_fold_down_desks_rows_and_starts_no_process(make_ctx, tool_state) -> None:
    root = tool_state.settings.render_root
    create_run({"package_id": "desk", "spec": desk()}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(root, "desk", 1))
    launched_before = len(tool_state.launched)

    text = run({"package_id": "desk"}, make_ctx())

    parts, hardware, _ = custom_derive.derive(desk())
    assert text.startswith("Cut list for desk version 1:")
    for part in parts:
        assert f"- {part['id']}: {part['qty']} × {part['l']} × {part['w']} × {part['t']} mm" in text
    assert f"Parts: {len(parts)} rows, {sum(p['qty'] for p in parts)} pieces in all" in text
    assert f"Hardware: {len(hardware)} lines" in text
    assert len(tool_state.launched) == launched_before


def test_a_missing_package_or_version_is_a_stated_refusal(make_ctx) -> None:
    assert "no package" in run({"package_id": "ghost"}, make_ctx())


def test_a_version_that_does_not_exist_is_refused(make_ctx, tool_state) -> None:
    from app.packages import service

    service.create_version(tool_state.settings.render_root, "desk", desk(), lambda version: None)
    assert "has no version 7" in run({"package_id": "desk", "version": 7}, make_ctx())
