"""design-agents: the Designer's `approve_version` — the conversation's latest built version is
approved on the owner's yes (place-piece-from-owner-words)."""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import DECLINED
from app.agent.tools import all_tools, loaded_plugins
from app.agent.tools.base import Confirmation
from app.blender import storage
from plugins.approve_version.tool import preview, run
from tests.test_duplicate_piece import make_source


def _built(state) -> None:
    make_source(state)
    storage.write_status(storage.version_dir(state.settings.render_root, "sideboard-1200", 1), status="succeeded")


def _approved(state) -> int | None:
    with Session(state.engine) as session:
        return house_file.approved_version_of(session, "sideboard-1200")


def test_the_plugin_is_loaded_for_the_designer_and_cannot_be_switched_off() -> None:
    assert "approve_version" in all_tools()
    plugin = loaded_plugins().by_name["approve_version"]
    assert plugin.agents == ("designer",)
    assert DECLINED["approve_version"] == "The version was not approved."


def test_the_owner_is_asked_and_nothing_changes_before_yes(make_ctx, tool_state) -> None:
    _built(tool_state)
    shown = preview({}, make_ctx(package_id="sideboard-1200"))
    assert isinstance(shown, Confirmation) and shown.subject == "approve_version"
    assert shown.summary == "Approve version 1 of Sideboard?"
    assert run({}, make_ctx(package_id="sideboard-1200")).startswith("this action needs the owner's confirmation")
    assert _approved(tool_state) is None


def test_yes_approves_the_latest_version(make_ctx, tool_state) -> None:
    _built(tool_state)
    output = run({}, replace(make_ctx(package_id="sideboard-1200"), approved=True))
    assert output.text == "Version 1 of Sideboard is approved."
    assert _approved(tool_state) == 1


def test_an_approved_version_is_not_asked_again(make_ctx, tool_state) -> None:
    _built(tool_state)
    run({}, replace(make_ctx(package_id="sideboard-1200"), approved=True))
    assert preview({}, make_ctx(package_id="sideboard-1200")) == "Version 1 is already approved."


def test_a_version_still_building_is_not_approved(make_ctx, tool_state) -> None:
    make_source(tool_state)
    output = run({}, replace(make_ctx(package_id="sideboard-1200"), approved=True))
    assert output == "Not approved: version 1 must be built before it can be approved."
    assert _approved(tool_state) is None


def test_the_model_passes_no_piece_or_version(make_ctx, tool_state) -> None:
    _built(tool_state)
    refused = preview({"version": 1}, make_ctx(package_id="sideboard-1200"))
    assert isinstance(refused, str) and refused.startswith("invalid arguments")
