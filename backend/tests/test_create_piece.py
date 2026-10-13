"""design-agents: the Designer's `create_piece` — validate, preview, confirm, build."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.create_piece import preview, run
from app.blender import storage
from tests.api_helpers import desk
from tests.conftest import wait_for_status


def arguments(package_id: str = "hall-bench", **spec_changes) -> dict:
    return {"package_id": package_id, "spec": {**desk(), **spec_changes}}


def test_a_valid_document_is_previewed_with_its_size_and_counts(make_ctx) -> None:
    shown = preview(arguments(), make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "create_piece"
    assert shown.proposal["package_id"] == "hall-bench"
    assert shown.proposal["modules"] == 1
    assert shown.proposal["cut_list_rows"] > 0
    assert "mm (w × h × d)" in shown.summary
    assert "hardware lines" in shown.summary


def test_previewing_creates_nothing(make_ctx, tool_state) -> None:
    preview(arguments(), make_ctx())
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == []


def test_yes_records_the_piece_and_version_one_and_starts_the_build(make_ctx, tool_deps, tool_state) -> None:
    ctx = replace(make_ctx(), approved=True, brief={"room": "Hall", "budget_eur": 400})
    output = run(arguments(), ctx)
    assert output.update == {"package_id": "hall-bench"}
    folder = storage.version_dir(tool_state.settings.render_root, "hall-bench", 1)
    assert (folder / "input.json").is_file()
    wait_for_status(folder)
    with tool_deps.session() as session:
        listing = {p["package_id"]: p for p in house_file.pieces(session, tool_state.settings.render_root)}
    assert listing["hall-bench"]["brief"] == {"room": "Hall", "budget_eur": 400}
    assert listing["hall-bench"]["versions"][0]["version"] == 1
    assert listing["hall-bench"]["versions"][0]["revised_from"] is None


def test_without_approval_nothing_is_created(make_ctx, tool_state) -> None:
    assert "confirmation" in run(arguments(), make_ctx())
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == []


def test_a_package_id_already_in_use_is_refused(make_ctx) -> None:
    run(arguments(), replace(make_ctx(), approved=True))
    refused = preview(arguments(), make_ctx())
    assert isinstance(refused, str)
    assert "already in use" in refused


def test_a_second_piece_on_a_bound_conversation_is_refused(make_ctx, tool_deps) -> None:
    from uuid import uuid4

    thread_id = uuid4()
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Hall", package_id="hall-bench")
        thread_id = thread.id
        session.commit()
    refused = preview(arguments("shelf"), make_ctx(thread_id=thread_id))
    assert isinstance(refused, str)
    assert "hall-bench" in refused
    assert "Create A New Piece" in refused


def test_create_on_an_unbound_thread_binds_it(make_ctx, tool_deps, tool_state) -> None:
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "New")
        thread_id = thread.id
        session.commit()
    ctx = replace(make_ctx(thread_id=thread_id), approved=True, brief={"budget_eur": 400})
    output = run(arguments(), ctx)
    assert output.update == {"package_id": "hall-bench"}
    with tool_deps.session() as session:
        assert house_file.get_thread(session, thread_id).package_id == "hall-bench"


def test_an_invalid_package_id_is_refused(make_ctx) -> None:
    assert isinstance(preview(arguments("Not A Slug"), make_ctx()), str)


def test_an_invalid_document_skips_the_pause_naming_the_field(make_ctx) -> None:
    document = desk()
    document["modules"][0]["width"] = 0
    refused = preview({"package_id": "bad", "spec": document}, make_ctx())
    assert isinstance(refused, str)
    assert "modules.0.width" in refused


def test_an_unknown_field_is_refused_by_name_and_recorded_with_the_owners_words(
    make_ctx, tool_deps, tool_state
) -> None:
    document = desk()
    document["modules"][0]["bevel_mm"] = 3
    ctx = make_ctx(last_message="I'd like a bevelled front edge")
    refused = preview({"package_id": "bevelled", "spec": document}, ctx)
    assert isinstance(refused, str)
    assert "bevel_mm" in refused
    assert "Do not offer to write Blender code" in refused
    assert storage.versions(tool_state.settings.render_root, "bevelled") == []
    with tool_deps.session() as session:
        requests = house_file.open_extension_requests(session)
    assert [r.field for r in requests] == ["modules[0].bevel_mm"]
    assert requests[0].request == "I'd like a bevelled front edge"
    assert requests[0].package_id == "bevelled"


def test_no_build_is_possible_without_the_loop(make_ctx, tool_state) -> None:
    tool_state.loop = None
    refused = preview(arguments(), make_ctx())
    assert isinstance(refused, str)
    assert "build queue" in refused


SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]


def _thread_in(tool_deps, *, room: str | None = None, apartment: str | None = None):
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Bench")
        if room:
            house_file.set_thread_room(session, thread.id, house_file.upsert_room(session, room, SQUARE, 2500))
        if apartment:
            flat = house_file.upsert_apartment(
                session, apartment, 2550, 120,
                [{"name": "Living", "corners_mm": SQUARE, "height_mm": None, "openings": []}],
            )
            house_file.set_thread_apartment(session, thread.id, flat)
        session.commit()
        return thread.id


def _piece_room(tool_deps, package_id: str) -> str | None:
    with tool_deps.session() as session:
        return house_file.piece_room_name(session, package_id)


def test_a_piece_is_recorded_in_the_conversations_confirmed_room(make_ctx, tool_deps) -> None:
    thread = _thread_in(tool_deps, room="Hall")
    run(arguments("shoe-bench"), replace(make_ctx(thread_id=thread), approved=True))
    assert _piece_room(tool_deps, "shoe-bench") == "Hall"


def test_the_briefs_room_wins_over_the_confirmed_one(make_ctx, tool_deps) -> None:
    thread = _thread_in(tool_deps, room="Hall")
    with tool_deps.session() as session:
        house_file.upsert_room(session, "Wohnen", SQUARE, 2600)
        session.commit()
    ctx = replace(make_ctx(thread_id=thread), approved=True, brief={"room": "Wohnen"})
    run(arguments("shoe-bench"), ctx)
    assert _piece_room(tool_deps, "shoe-bench") == "Wohnen"


def test_a_piece_without_any_room_stays_unassigned(make_ctx, tool_deps) -> None:
    thread = _thread_in(tool_deps)
    run(arguments("shoe-bench"), replace(make_ctx(thread_id=thread), approved=True))
    assert _piece_room(tool_deps, "shoe-bench") is None


def test_an_apartment_without_a_room_is_refused_with_the_question_and_no_pause(make_ctx, tool_deps, tool_state) -> None:
    thread = _thread_in(tool_deps, apartment="Wohnung")
    refused = preview(arguments("shoe-bench"), make_ctx(thread_id=thread))
    assert isinstance(refused, str)
    assert "Wohnung" in refused and "which room" in refused
    assert storage.versions(tool_state.settings.render_root, "shoe-bench") == []
    assert "which room" in run(arguments("shoe-bench"), replace(make_ctx(thread_id=thread), approved=True))
    assert storage.versions(tool_state.settings.render_root, "shoe-bench") == []


def test_an_apartment_with_one_of_its_rooms_in_the_brief_is_accepted(make_ctx, tool_deps) -> None:
    thread = _thread_in(tool_deps, apartment="Wohnung")
    ctx = replace(make_ctx(thread_id=thread), approved=True, brief={"room": "Living"})
    run(arguments("shoe-bench"), ctx)
    assert _piece_room(tool_deps, "shoe-bench") == "Living"
