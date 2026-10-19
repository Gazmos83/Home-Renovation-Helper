"""view-piece-in-room: `ask_placement` asks where the piece goes, checks it and stores it."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Questions, ToolOutput
from app.blender import storage
from app.blender.custom_build import derive as custom_derive
from app.packages import service
from app.packages.placements import read_placement
from plugins.ask_placement.tool import (
    DISTANCE_QUESTION,
    WALL_QUESTION,
    offset_from_left,
    preview,
    run,
)
from tests.api_helpers import desk

# Five walls, counter-clockwise: 6000, 3000, 3354, 3354 and 3000 mm.
WOHNEN = [[0, 0], [6000, 0], [6000, 3000], [3000, 4500], [0, 3000]]
WIDTH = float(custom_derive.overall(desk())["w"])


def _setup(tool_deps, tool_state):
    service.create_version(tool_state.settings.render_root, "bench", desk(), lambda version: None)
    with tool_deps.session() as session:
        room = house_file.upsert_room(session, "Wohnen", WOHNEN, 2600)
        thread = house_file.create_thread(session, "Bench", package_id="bench")
        house_file.set_thread_room(session, thread.id, room)
        session.commit()
        return thread.id


def _ctx(make_ctx, thread, answers=None, declined=None):
    ctx = make_ctx(thread_id=thread, package_id="bench")
    if declined is not None:
        return replace(ctx, answer={"declined": declined})
    return replace(ctx, answer={"answers": answers or []})


def _stored(tool_state):
    return read_placement(storage.version_dir(tool_state.settings.render_root, "bench", 1), "Wohnen")


def test_the_questions_are_written_by_code_with_each_wall_and_its_length(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    asked = preview({}, make_ctx(thread_id=thread, package_id="bench"))
    assert isinstance(asked, Questions)
    assert asked.layout == "room"
    first, second = asked.questions
    assert first["text"] == WALL_QUESTION == "Where would you like to place the piece? Check out the Room layout."
    assert first["choices"] == [
        "Wall 1 (6000 mm)", "Wall 2 (3000 mm)", "Wall 3 (3354 mm)", "Wall 4 (3354 mm)", "Wall 5 (3000 mm)",
    ]
    assert second == {"text": DISTANCE_QUESTION, "unit": "mm", "choices": []}
    assert second["text"] == "How far from the left end of that wall should the piece start? (seen facing the wall)"


def test_the_model_passes_no_wall_or_offset(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    refused = preview({"wall": 1, "offset_mm": 300}, make_ctx(thread_id=thread, package_id="bench"))
    assert isinstance(refused, str) and refused.startswith("invalid arguments")


def test_the_left_end_is_the_walls_end_corner(make_ctx, tool_deps, tool_state) -> None:
    # Facing wall 1 (from (0, 0) to (6000, 0)) from inside the room, east is on the left.
    assert offset_from_left(6000, 300, 800) == 4900


def test_a_place_that_fits_is_stored_and_reported(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    result = run({}, _ctx(make_ctx, thread, ["Wall 1 (6000 mm)", "300"]))
    assert isinstance(result, ToolOutput)
    assert result.text.startswith("Placement saved for Wohnen: wall 1, 300 mm from the left end.")
    assert result.update == {"placement_ready": True}
    stored = _stored(tool_state)
    assert stored["wall"] == 0 and stored["left_mm"] == 300
    assert stored["offset_mm"] == 6000 - 300 - WIDTH
    assert stored["scene"]["placement"]["wall"] == 0
    assert stored["scene"]["placement"]["offset_mm"] == 6000 - 300 - WIDTH


def test_a_typed_wall_number_is_read(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    result = run({}, _ctx(make_ctx, thread, ["wall 2", "100 mm"]))
    assert isinstance(result, ToolOutput)
    assert _stored(tool_state)["wall"] == 1


def test_a_place_too_wide_is_refused_in_plain_words_and_nothing_is_stored(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    result = run({}, _ctx(make_ctx, thread, ["Wall 2 (3000 mm)", f"{3000 - WIDTH + 150:g}"]))
    assert isinstance(result, str)
    assert "the piece is 150 mm too wide for wall 2 (3000 mm)" in result
    assert "ask_placement again" in result
    assert _stored(tool_state) is None


def test_an_unknown_wall_is_asked_again(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    result = run({}, _ctx(make_ctx, thread, ["Wall 9", "100"]))
    assert "Wohnen has walls 1 to 5" in result
    assert _stored(tool_state) is None


def test_a_declined_set_returns_the_owners_words(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    result = run({}, _ctx(make_ctx, thread, declined="put it next to the sofa"))
    assert isinstance(result, str)
    assert "put it next to the sofa" in result
    assert _stored(tool_state) is None


def test_without_a_room_nothing_is_asked(make_ctx, tool_deps, tool_state) -> None:
    service.create_version(tool_state.settings.render_root, "bench", desk(), lambda version: None)
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Bench", package_id="bench").id
        session.commit()
    refused = preview({}, make_ctx(thread_id=thread, package_id="bench"))
    assert refused == "This conversation has no room yet; ask the owner which room the piece is for."


# --- a wall-hung piece (conversation-continuity) --------------------------------------------


def test_a_hung_piece_is_also_asked_how_far_below_the_ceiling(make_ctx, tool_deps, tool_state) -> None:
    from plugins.ask_placement.tool import GAP_QUESTION

    thread = _setup(tool_deps, tool_state)
    asked = preview({"hung": True}, replace(make_ctx(thread_id=thread, package_id="bench"), last_message="Hang it on the wall"))
    assert isinstance(asked, Questions)
    assert asked.questions[2] == {"text": GAP_QUESTION, "unit": "mm", "choices": []}
    assert len(preview({}, make_ctx(thread_id=thread, package_id="bench")).questions) == 2


def test_a_hung_place_is_stored_with_its_height(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    height = float(custom_derive.overall(desk())["h"])
    ctx = replace(_ctx(make_ctx, thread, ["Wall 2 (3000 mm)", "0", "0"]), last_message="hang it up")
    result = run({"hung": True}, ctx)
    assert isinstance(result, ToolOutput)
    assert f"hung with its top 0 mm below the ceiling and its underside at {2600 - height:g} mm" in result.text
    assert _stored(tool_state)["mount_height_mm"] == 2600 - height


# --- values the owner already stated (place-piece-from-owner-words) -------------------------


def _said(make_ctx, thread, message, answers=None):
    ctx = replace(make_ctx(thread_id=thread, package_id="bench"), last_message=message)
    return replace(ctx, answer={"answers": answers}) if answers is not None else ctx


def test_a_fully_stated_place_is_not_asked_and_is_stored(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    message = "Please place the sideboard along wall 2 0 mm from wall 3."
    args = {"wall": 2, "distance_mm": 0, "from_wall": 3}
    assert preview(args, _said(make_ctx, thread, message)) is None
    result = run(args, _said(make_ctx, thread, message))
    assert isinstance(result, ToolOutput)
    assert result.text.startswith("Placement saved for Wohnen: wall 2, 0 mm from the left end.")
    assert _stored(tool_state)["wall"] == 1 and _stored(tool_state)["left_mm"] == 0


def test_a_distance_from_the_previous_wall_is_from_the_right_end(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    message = "wall 1, 300 mm from wall 5"
    args = {"wall": 1, "distance_mm": 300, "from_wall": 5}
    assert preview(args, _said(make_ctx, thread, message)) is None
    assert isinstance(run(args, _said(make_ctx, thread, message)), ToolOutput)
    assert _stored(tool_state)["left_mm"] == 6000 - 300 - WIDTH


def test_a_distance_from_a_wall_not_next_to_it_is_asked(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    asked = preview({"wall": 2, "distance_mm": 300, "from_wall": 4}, _said(make_ctx, thread, "wall 2, 300 mm from wall 4"))
    assert isinstance(asked, Questions)
    assert [q["text"] for q in asked.questions] == [
        f"The distance has to be measured from a wall next to wall 2 (wall 3 or wall 1). {DISTANCE_QUESTION}"
    ]


def test_only_the_missing_question_is_asked_and_its_answer_is_used(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    asked = preview({"wall": 2}, _said(make_ctx, thread, "put it on wall 2"))
    assert isinstance(asked, Questions)
    assert [q["text"] for q in asked.questions] == [DISTANCE_QUESTION]
    assert isinstance(run({"wall": 2}, _said(make_ctx, thread, "put it on wall 2", ["100"])), ToolOutput)
    assert _stored(tool_state)["wall"] == 1 and _stored(tool_state)["left_mm"] == 100


def test_a_number_the_owner_did_not_write_is_asked(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    asked = preview({"wall": 2, "distance_mm": 500}, _said(make_ctx, thread, "put it on wall 2"))
    assert [q["text"] for q in asked.questions] == [DISTANCE_QUESTION]
    asked = preview({"wall": 7, "distance_mm": 0}, _said(make_ctx, thread, "wall 7 0 mm"))
    assert [q["text"] for q in asked.questions] == [WALL_QUESTION]


def test_a_hung_place_asks_only_the_missing_gap(make_ctx, tool_deps, tool_state) -> None:
    from plugins.ask_placement.tool import GAP_QUESTION

    thread = _setup(tool_deps, tool_state)
    message = "hang it on wall 2, 0 mm from wall 3"
    args = {"hung": True, "wall": 2, "distance_mm": 0, "from_wall": 3}
    asked = preview(args, _said(make_ctx, thread, message))
    assert [q["text"] for q in asked.questions] == [GAP_QUESTION]
    assert isinstance(run(args, _said(make_ctx, thread, message, ["0"])), ToolOutput)
    assert _stored(tool_state)["left_mm"] == 0


def test_hung_without_the_owners_words_places_the_piece_standing(make_ctx, tool_deps, tool_state) -> None:
    thread = _setup(tool_deps, tool_state)
    message = "Please place the sideboard along wall 2 0 mm from wall 3."
    args = {"hung": True, "wall": 2, "distance_mm": 0, "from_wall": 3}
    assert preview(args, _said(make_ctx, thread, message)) is None
    result = run(args, _said(make_ctx, thread, message))
    assert "hung" not in result.text
    assert _stored(tool_state).get("mount_height_mm") is None


def test_a_piece_marked_wall_mounted_is_asked_its_gap(make_ctx, tool_deps, tool_state) -> None:
    from plugins.ask_placement.tool import GAP_QUESTION

    spec = desk()
    for module in spec["modules"]:
        module["mounting"] = "wall"
    service.create_version(tool_state.settings.render_root, "shelf", spec, lambda version: None)
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Shelf", package_id="shelf")
        house_file.set_thread_room(session, thread.id, house_file.upsert_room(session, "Wohnen", WOHNEN, 2600))
        session.commit()
        thread_id = thread.id
    ctx = replace(make_ctx(thread_id=thread_id, package_id="shelf"), last_message="wall 2, 0 mm from wall 3")
    asked = preview({"wall": 2, "distance_mm": 0, "from_wall": 3}, ctx)
    assert [q["text"] for q in asked.questions] == [GAP_QUESTION]
