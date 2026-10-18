"""design-agents: instruction files, their headers and their faults."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.agent.instructions import (
    AGENT_NAMES,
    INSTRUCTIONS_DIR,
    InstructionError,
    load_instructions,
)
from app.agent.models.routing import SLOTS


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "instructions"
    target.mkdir()
    for name in AGENT_NAMES:
        shutil.copy(INSTRUCTIONS_DIR / f"{name}.md", target / f"{name}.md")
    return target


def test_all_instruction_files_load() -> None:
    loaded = load_instructions()
    assert list(loaded) == [
        "foreman", "intake", "designer", "builder", "lighting", "reviewer", "researcher",
    ]
    for name, instruction in loaded.items():
        assert instruction.name == name
        assert instruction.slot == name
        assert instruction.text


def test_each_agent_names_exactly_its_tools() -> None:
    loaded = load_instructions()
    assert loaded["foreman"].tools == ()
    assert loaded["lighting"].tools == (
        "start_detail_pass", "run_detail_script", "detail_screenshot", "render_detail",
        "record_render_feedback",
    )
    assert loaded["intake"].tools == ("record_brief", "record_plan", "confirm_room", "ask_owner", "read_help")
    assert set(loaded["designer"].tools) == {
        "create_piece", "import_design", "import_design_version", "revise_package", "rebuild_piece", "cut_list", "room_fit", "compose_room",
        "read_room_version_dimensions", "edit_decisions", "record_version_verdict", "search_guidelines",
        "ask_owner", "ask_placement", "search_engineering_knowledge", "record_assessment_inputs", "calculate_engineering",
        "get_engineering_report",
    }
    assert set(loaded["builder"].tools) == {
        "blender_build", "build_shell", "render_turntable", "restyle_render", "record_render_feedback",
    }
    assert loaded["reviewer"].tools == ("revision_review",)
    assert set(loaded["researcher"].tools) == {
        "search_catalog_knowledge", "check_live_listing", "compare_products", "price_cut_list", "manage_remnants",
        "search_guidelines", "read_room_version_dimensions", "search_engineering_knowledge",
        "record_assessment_inputs", "calculate_engineering", "get_engineering_report",
    }


def test_guideline_search_is_shared_with_the_researcher() -> None:
    from app.agent.tools import tool_roles

    assert tool_roles()["search_guidelines"] == ("designer", "researcher")


def test_room_version_dimensions_is_shared_with_the_researcher() -> None:
    from app.agent.tools import tool_roles

    assert tool_roles()["read_room_version_dimensions"] == ("designer", "researcher")


def test_the_designer_and_builder_never_offer_blender_code() -> None:
    loaded = load_instructions()
    for name in ("intake", "designer", "builder"):
        assert "Never offer to write Blender code" in loaded[name].text or "Never write, show or run Blender code" in loaded[name].text


def test_the_designer_relays_the_version_limit_and_never_deletes() -> None:
    text = load_instructions()["designer"].text
    line = next(line for line in text.splitlines() if "15 versions" in line)
    assert "pass the refusal on as it is" in line
    assert "Pieces page or in the Piece panel" in line
    assert "never offer to delete a version yourself" in line


def test_the_designer_knows_shelf_spacing_and_dividers() -> None:
    text = load_instructions()["designer"].text
    for field in ("shelf_spacing_mm", "shelf_positions_mm", "dividers", "divider_positions_mm"):
        assert f"`{field}`" in text
    assert '"shelf_spacing_mm": 355' in text and "Never compute shelf heights" in text


def test_the_designer_knows_side_folds() -> None:
    text = load_instructions()["designer"].text
    for field in ("side_folds", "from_mm", "along", "angle_deg", "towards"):
        assert f"`{field}`" in text
    assert "26 degree bend from 1100 mm" in text
    assert "`along: height`" in text and "`towards: inside`" in text
    assert "may carry overlay fronts, adjustable shelves and dividers" in text
    assert "Dividers on a folded module are not expressible" not in text
    assert "Never tell the owner there is no field for a bend angle" in text
    assert "piece summary" in text
    assert "An edge bevel has no field" in text


def test_the_designer_knows_divider_spans_and_shelf_kinds() -> None:
    text = load_instructions()["designer"].text
    for field in ("divider_spans", "from_board", "to_board", "shelf_kinds"):
        assert f"`{field}`" in text
    assert '"divider_spans": [{"from_board": 4, "to_board": "top"}]' in text
    assert "Never tell the owner a partial-height divider cannot be made" in text
    assert "Only a fixed shelf can hold a divider" in text
    assert "Never change a shelf's kind without the owner's yes" in text
    assert "`search_guidelines`" in text and "recommended position" in text


def test_the_designer_knows_per_shelf_depths() -> None:
    text = load_instructions()["designer"].text
    for field in ("shelf_depths_mm", "shelf_depth_align"):
        assert f"`{field}`" in text
    assert '"shelf_depths_mm": [null, 500, null, null]' in text
    assert "Never tell the owner there is no per-shelf depth field" in text
    assert "never deepen the whole module" in text
    assert "needs no separate `y` or envelope change" in text
    assert "never propose deepening the module to hold it" in text
    assert "Never clear or change a module's `side_folds` to satisfy another rule" in text
    assert "When the app refuses a change because of a fold, tell the owner" in text


def test_the_foreman_routes_a_side_fold_to_the_designer() -> None:
    text = load_instructions()["foreman"].text
    line = next(line for line in text.splitlines() if line.startswith("- `designer`:"))
    assert "fold or bend in a carcass side" in line


def test_revise_package_names_side_folds_as_a_panel_bend() -> None:
    from app.agent.tools.revise_package import revise_package
    from app.blender.schemas import ModuleChange

    assert "side_folds" in revise_package.description
    assert "bend" in revise_package.description.lower()
    folded = ModuleChange.model_json_schema()["properties"]["side_folds"]
    description = folded.get("description") or folded.get("anyOf", [{}])[0].get("description", "")
    assert "carcass-side" in description


def _break(tmp_path: Path, name: str, edit) -> str:
    directory = _copy(tmp_path)
    path = directory / f"{name}.md"
    path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(InstructionError) as error:
        load_instructions(directory)
    return str(error.value)


def test_an_unknown_tool_fails_naming_the_file(tmp_path: Path) -> None:
    message = _break(
        tmp_path, "designer", lambda text: text.replace("ask_placement]", "ask_placement, run_bpy]", 1)
    )
    assert message.startswith("designer.md:")
    assert "run_bpy" in message


def test_empty_text_fails_naming_the_file(tmp_path: Path) -> None:
    message = _break(tmp_path, "intake", lambda text: text.split("---\n")[1].join(["---\n", "---\n"]))
    assert message.startswith("intake.md:")
    assert "empty" in message


def test_the_sentinel_in_the_text_fails_naming_the_file(tmp_path: Path) -> None:
    message = _break(tmp_path, "builder", lambda text: text + "\n[[[UNTRUSTED_SOURCE\n")
    assert message.startswith("builder.md:")
    assert "reserved delimiter" in message


def test_a_slot_missing_from_routing_fails_naming_the_file(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    slots = [slot for slot in SLOTS if slot != "builder"]
    with pytest.raises(InstructionError, match=r"builder\.md: the slot 'builder'"):
        load_instructions(directory, slots=slots)


def test_a_missing_file_fails_naming_it(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    (directory / "builder.md").unlink()
    with pytest.raises(InstructionError, match=r"builder\.md: the instruction file is missing"):
        load_instructions(directory)


def test_a_missing_researcher_file_fails_naming_it(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    (directory / "researcher.md").unlink()
    with pytest.raises(InstructionError, match=r"researcher\.md: the instruction file is missing"):
        load_instructions(directory)


def test_a_header_name_that_differs_from_the_file_fails(tmp_path: Path) -> None:
    message = _break(tmp_path, "foreman", lambda text: text.replace("name: foreman", "name: intake", 1))
    assert message.startswith("foreman.md:")


def test_a_tool_shared_with_another_agent_may_be_named_by_it_but_a_stranger_may_not(tmp_path: Path) -> None:
    from app.agent.instructions import parse_instruction

    header = "---\nname: {name}\nslot: {name}\ntools: [{tool}]\n---\nYou are the {name}."
    roles = {"record_render_feedback": ("builder", "lighting"), "cut_list": "designer"}
    tools = list(roles)
    for name in ("builder", "lighting"):
        parsed = parse_instruction(
            header.format(name=name, tool="record_render_feedback"),
            filename=f"{name}.md", known_tools=tools, tool_roles=roles,
        )
        assert parsed.tools == ("record_render_feedback",)
    with pytest.raises(InstructionError, match="belongs to builder and lighting, not reviewer"):
        parse_instruction(
            header.format(name="reviewer", tool="record_render_feedback"),
            filename="reviewer.md", known_tools=tools, tool_roles=roles,
        )
    with pytest.raises(InstructionError, match="belongs to designer, not builder"):
        parse_instruction(
            header.format(name="builder", tool="cut_list"),
            filename="builder.md", known_tools=tools, tool_roles=roles,
        )


def test_the_foreman_sends_room_corrections_to_intake_and_piece_changes_to_the_designer() -> None:
    text = load_instructions()["foreman"].text
    assert "goes to `intake` even after the numbers are confirmed or a piece exists" in text
    intake_line = next(line for line in text.splitlines() if line.startswith("- `intake`"))
    designer_line = next(line for line in text.splitlines() if line.startswith("- `designer`"))
    assert "corner angles" in intake_line and "openings" in intake_line
    assert "the piece itself" in designer_line and "numbers are confirmed" not in designer_line


def test_the_foreman_sends_questions_about_what_the_owner_sees_to_the_reviewer() -> None:
    text = load_instructions()["foreman"].text
    assert (
        "`reviewer`: the owner asks whether something they see in the inspector "
        "(a view such as front or exploded, a module or a part) is right, "
        "or wants the piece checked against the brief."
    ) in text
    assert (
        "A request to change what they see goes to `designer`; "
        "a question whether it is right goes to `reviewer`."
    ) in text


def test_the_reviewer_names_inspector_views_and_passes_the_focus() -> None:
    text = load_instructions()["reviewer"].text
    naming = "Name what you looked at by the inspector's views: front, side, top."
    assert naming in text and "exploded" not in naming
    assert (
        "You have no exploded image; for a question about the exploded view, say so "
        "and answer from the spec's parts and the views you have."
    ) in text
    assert "Pass the owner's question, in their words, as `focus`." in text
    assert "which view" in text and "which image" not in text


PLAIN_REFUSAL = (
    "If a tool result says nothing was done, tell the owner plainly that nothing was saved or changed and why; "
    "never say a tool failed or would not take an update."
)
NO_LATER_PROMISE = "Never promise to tell the owner later"


def test_every_specialist_passes_a_refusal_on_plainly() -> None:
    loaded = load_instructions()
    for name in ("intake", "designer", "builder", "lighting", "reviewer", "researcher"):
        assert PLAIN_REFUSAL in loaded[name].text, name


def test_no_specialist_promises_to_report_back_after_the_turn() -> None:
    loaded = load_instructions()
    for name in ("designer", "builder", "lighting", "reviewer"):
        assert NO_LATER_PROMISE in loaded[name].text, name
    for name in ("designer", "builder"):
        assert "status shows in the conversation's Piece panel" in loaded[name].text, name
    for name, instruction in loaded.items():
        lowered = instruction.text.lower()
        assert "i'll tell you" not in lowered and "let you know" not in lowered, name


def test_the_designer_composes_rooms_and_the_builder_renders_them() -> None:
    loaded = load_instructions()
    designer, builder = loaded["designer"].text, loaded["builder"].text
    assert "`compose_room`" in designer and "approved piece versions only" in designer
    assert "state the refusal plainly" in designer
    assert "pass `composition`" in builder and "no longer approved" in builder


def test_intake_lists_note_conflicts_in_a_table_before_proposing() -> None:
    text = load_instructions()["intake"].text
    assert "attaches a text note" in text
    assert "table with the columns What, Note, Other value and Source" in text
    assert "Never settle a disagreement silently" in text


def test_the_designer_composes_an_empty_room_on_request() -> None:
    text = load_instructions()["designer"].text
    assert "When the owner wants the room with no furniture, call `compose_room` with the room and an empty item list." in text


def test_the_designer_restates_a_revision_and_asks_before_calling_the_tool() -> None:
    text = load_instructions()["designer"].text
    assert "first restate the changes you understood as a short list" in text
    assert "ask whether anything else should change" in text
    assert "Call `revise_package` only once the owner says the list is complete" in text
    assert "every change asked for since the last created revision in that one call" in text
    assert "add it to the list and ask again" in text
    assert "treat the reason as one more change: restate the whole list and ask again" in text
    assert "Do not call `revise_package` again in that reply." in text
    assert "write the new list starting from the summary's" in text
    assert "Never resend the whole document." in text


def test_the_designer_restates_a_composition_change_and_asks_before_calling_the_tool() -> None:
    text = load_instructions()["designer"].text
    assert "To change a room or apartment whose composition already has a version" in text
    assert "one line per item added, moved or removed, naming the item by its id" in text
    assert "Call `compose_room` only once the owner says the list is complete" in text
    assert "every change asked for since the composition's latest version in that one call" in text
    assert "Do not call `compose_room` again in that reply." in text
    assert "A first composition, with no version yet, needs no restating." in text


def test_intake_reuses_a_stored_room_only_through_a_confirmation() -> None:
    text = load_instructions()["intake"].text
    assert "Never ask for what it already says about this conversation's confirmed room." in text
    assert "Never ask for what it already says.\n" not in text
    assert "A stored room or apartment that this conversation has not confirmed is never assumed" in text
    assert "Offer it with `confirm_room`, which shows its stored measurements" in text
    assert "use none of its figures before the owner's yes" in text


def test_intake_takes_the_room_path_for_a_room_only_wish() -> None:
    text = load_instructions()["intake"].text
    assert "When the owner wants a room designed or furnished rather than a piece, take the room path." in text
    assert "ask what the room should hold" in text
    assert "Never ask which piece to design, or a piece's purpose, size or budget" in text
    assert "never call `record_brief` for a room-only wish" in text
    assert "offer to compose the room with what it should hold, not to design a piece" in text


def test_the_foreman_flags_composing_a_room_apart_from_a_piece_wish() -> None:
    text = load_instructions()["foreman"].text
    assert "Set `composes_room` to true only when the owner wants a room furnished or composed" in text
    assert "A wish for a new piece is never composing a room." in text


def test_the_foreman_flags_an_open_question_apart_from_a_request() -> None:
    text = load_instructions()["foreman"].text
    assert "Set `open_question` to true only when the owner asks a question or thinks aloud about a piece" in text
    assert "\"I'd like to build a kitchen counter, how tall should it be?\" is an open question" in text
    assert "\"Can you design a shoe bench for me?\" is not, it is a request" in text


def test_the_designer_fills_requested_with_the_owners_lengths() -> None:
    text = load_instructions()["designer"].text
    assert "Fill `requested` in every `revise_package` call with each length with a unit" in text
    assert "quote the owner's own words" in text
    assert "is added to the value in the piece summary" in text
    assert "Use target `none` for a length that is not about the piece" in text
    assert "never invent a value" in text


def test_the_designer_changes_the_decisions_note_only_when_asked() -> None:
    text = (Path(__file__).resolve().parent.parent / "app" / "agent" / "instructions" / "designer.md").read_text()
    assert "only when the owner's own message asks for that" in text
    assert "never change it unprompted" in text
    assert "nothing is written before yes" in text


def test_the_designer_goes_by_the_stated_front_positions() -> None:
    text = load_instructions()["designer"].text
    assert "where each front sits" in text and "not by the brief or earlier messages" in text


def test_the_designer_lays_rugs_on_the_floor_layer() -> None:
    text = load_instructions()["designer"].text
    assert '`layer: "floor"`' in text and "may lie under other furniture" in text


def test_the_designer_knows_modelled_handles() -> None:
    text = load_instructions()["designer"].text
    assert "`handle`" in text and '{"kind": "bar", "length": 160}' in text
    assert "never also write a hardware line for a modelled handle" in text
    assert "A push-latch door takes no handle" in text


def test_the_designer_records_a_verdict_only_when_the_owner_gives_one() -> None:
    """version-verdict: the verdict tool and the open verdicts in the house file."""
    text = load_instructions()["designer"].text
    assert "`record_version_verdict`" in text
    assert "Never call it unprompted" in text
    assert "open verdicts" in text and "do not repeat them" in text


def test_the_foreman_sends_a_verdict_on_a_version_to_the_designer() -> None:
    text = load_instructions()["foreman"].text
    assert "a version of the piece is right or wrong" in text and "records the verdict" in text


def test_the_designer_knows_hanging_rails_and_import_corrections() -> None:
    text = load_instructions()["designer"].text
    assert "`hanging_rails`" in text and '`{"z": 1650}`' in text
    assert "use only a height the owner gave, and ask when there is none" in text
    assert "When an import preview lists hardware corrections, pass them on as they are" in text


def test_the_designer_offers_cited_suggestions_for_a_new_piece() -> None:
    """guideline-design-suggestions: cited style suggestions before the first draft."""
    text = load_instructions()["designer"].text
    line = next(line for line in text.splitlines() if "found no style guidance in the guidelines" in line)
    assert "`search_guidelines`" in line and "`create_piece`" in line
    assert "at most three" in line and "advice only" in line and "generator-extension" in line
    assert "revisions, imports or rebuilds" in line


def test_the_designer_knows_door_slats() -> None:
    text = load_instructions()["designer"].text
    for word in ("`slats`", "`count`", "`orientation`", "`margin_mm`", "`leaves`", "never write slats as extra parts"):
        assert word in text, word
    assert "pass that warning on to the owner" in text


def test_no_model_insists_on_a_room_the_conversation_declined() -> None:
    """optional-room-question: the app offers the room; Intake never asks it after a no."""
    loaded = load_instructions()
    intake = loaded["intake"].text
    assert "The app asks the owner whether they want to view the piece in a room; never ask that yourself." in intake
    assert "When the facts say the owner chose not to view this piece in a room, never ask for a room" in intake
    assert "Ask once whether the owner wants to name the room now" not in intake
    for name in ("foreman", "intake"):
        assert "Which room is this for?" not in loaded[name].text


def test_missing_information_is_asked_for_not_explained() -> None:
    """view-piece-in-room: ask, don't explain; never name internals to the owner."""
    loaded = load_instructions()
    for name in ("designer", "builder", "intake"):
        text = loaded[name].text
        assert "Ask, don't explain" in text
        assert "Never name a tool, a document, a field or a JSON key to the owner." in text
    assert "call `ask_placement`" in loaded["designer"].text
    builder = loaded["builder"].text
    assert "`in_room` true" in builder
    assert "room document" not in builder and "room_fit" not in builder


def test_the_designer_gives_one_door_its_own_material_without_splitting_the_pair() -> None:
    """door-leaf-materials: per-door colour is `leaf_materials`, never stacked entries."""
    text = load_instructions()["designer"].text
    assert "`leaf_materials`" in text
    assert "Never split a pair or row of doors into separate entries for this" in text
    assert "keep the front layout" in text


def test_the_foreman_treats_a_change_to_a_composed_room_as_composing() -> None:
    """room-change-goes-to-designer."""
    text = load_instructions()["foreman"].text
    assert "Moving, adding, removing or re-placing anything in a composed room is composing it" in text
    assert "Only a request to render or look at the room is `builder`." in text


def test_the_designer_takes_placed_sizes_from_the_note() -> None:
    """room-change-goes-to-designer."""
    text = load_instructions()["designer"].text
    assert "Take every placed item's size and position from the composition note and never ask the owner for them" in text
    assert "not a cut-list part's" in text


def test_the_builder_does_not_relay_a_room_change() -> None:
    """room-change-goes-to-designer."""
    text = load_instructions()["builder"].text
    assert "say in one sentence that the room has not been changed yet" in text
    assert "never offer to pass them on" in text
