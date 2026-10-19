"""design-agents: the Designer's `duplicate_piece` — check, preview, confirm, copy (duplicate-piece)."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import DECLINED
from app.agent.tools import all_tools, loaded_plugins
from app.agent.tools.base import Confirmation
from app.blender import storage
from app.db.models import Thread
from plugins.duplicate_piece.tool import preview, run
from tests.conftest import wait_for_status
from tests.test_duplicate_piece import make_source


def arguments(**changes) -> dict:
    return {"source_package_id": "sideboard-1200", "name": "Sideboard Hall", **changes}


def bound_thread(state) -> UUID:
    with Session(state.engine) as session:
        thread = house_file.create_thread(session, "Sideboard", package_id="sideboard-1200")
        session.commit()
        return thread.id


def test_the_plugin_is_loaded_for_the_designer() -> None:
    assert "duplicate_piece" in all_tools()
    assert loaded_plugins().by_name["duplicate_piece"].agents == ("designer",)


def test_a_valid_call_is_previewed_and_creates_nothing(make_ctx, tool_state) -> None:
    make_source(tool_state, versions=2)
    shown = preview(arguments(), make_ctx())
    assert isinstance(shown, Confirmation) and shown.subject == "duplicate_piece"
    assert shown.proposal["version"] == 2 and shown.proposal["package_id"] == "sideboard-hall"
    assert "sideboard-1200 version 2" in shown.summary and "mm (w × h × d)" in shown.summary
    assert storage.versions(tool_state.settings.render_root, "sideboard-hall") == []


def test_yes_in_the_pieces_own_conversation_makes_the_copy_and_keeps_the_binding(make_ctx, tool_state) -> None:
    make_source(tool_state)
    thread_id = bound_thread(tool_state)
    ctx = replace(make_ctx(), thread_id=thread_id, package_id="sideboard-1200", approved=True, slot="designer")
    output = run(arguments(), ctx)
    assert "sideboard-hall" in output.text and "/studio/workspace/" in output.text
    assert output.update == {}
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "sideboard-hall", 1))
    with Session(tool_state.engine) as session:
        assert session.get(Thread, thread_id).package_id == "sideboard-1200"
        copy_thread = house_file.thread_id_for_piece(session, "sideboard-hall")
        assert copy_thread is not None and str(copy_thread) in output.text
        assert house_file.version_row(session, "sideboard-hall", 1).slot == "designer"


def test_without_yes_nothing_is_created(make_ctx, tool_state) -> None:
    make_source(tool_state)
    run(arguments(), make_ctx())
    assert storage.versions(tool_state.settings.render_root, "sideboard-hall") == []
    assert DECLINED["duplicate_piece"] == "The piece was not duplicated."


def test_an_unknown_source_is_refused_naming_it(make_ctx, tool_state) -> None:
    shown = preview(arguments(source_package_id="nothing-here"), make_ctx())
    assert isinstance(shown, str) and "nothing-here" in shown


def test_a_taken_name_is_refused(make_ctx, tool_state) -> None:
    make_source(tool_state)
    shown = preview(arguments(name="SIDEBOARD"), make_ctx())
    assert isinstance(shown, str) and "already named" in shown
