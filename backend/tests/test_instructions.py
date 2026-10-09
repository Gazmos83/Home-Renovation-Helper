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
    assert loaded["intake"].tools == ("record_brief", "record_plan", "confirm_room", "ask_owner")
    assert set(loaded["designer"].tools) == {
        "create_piece", "import_design", "import_design_version", "revise_package", "rebuild_piece", "cut_list", "room_fit", "compose_room", "search_guidelines",
        "ask_owner",
    }
    assert set(loaded["builder"].tools) == {
        "blender_build", "build_shell", "render_turntable", "record_render_feedback",
    }
    assert loaded["reviewer"].tools == ("revision_review",)
    assert set(loaded["researcher"].tools) == {
        "search_catalog_knowledge", "check_live_listing", "compare_products", "price_cut_list", "manage_remnants",
        "search_guidelines",
    }


def test_guideline_search_is_shared_with_the_researcher() -> None:
    from app.agent.tools import tool_roles

    assert tool_roles()["search_guidelines"] == ("designer", "researcher")


def test_the_designer_and_builder_never_offer_blender_code() -> None:
    loaded = load_instructions()
    for name in ("intake", "designer", "builder"):
        assert "Never offer to write Blender code" in loaded[name].text or "Never write, show or run Blender code" in loaded[name].text


def test_the_designer_knows_shelf_spacing_and_dividers() -> None:
    text = load_instructions()["designer"].text
    for field in ("shelf_spacing_mm", "shelf_positions_mm", "dividers", "divider_positions_mm"):
        assert f"`{field}`" in text
    assert '"shelf_spacing_mm": 355' in text and "Never compute shelf heights" in text


def _break(tmp_path: Path, name: str, edit) -> str:
    directory = _copy(tmp_path)
    path = directory / f"{name}.md"
    path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(InstructionError) as error:
        load_instructions(directory)
    return str(error.value)


def test_an_unknown_tool_fails_naming_the_file(tmp_path: Path) -> None:
    message = _break(
        tmp_path, "designer", lambda text: text.replace("ask_owner]", "ask_owner, run_bpy]", 1)
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
        assert "status shows in the conversation's Project panel" in loaded[name].text, name
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


def test_the_designer_fills_requested_with_the_owners_lengths() -> None:
    text = load_instructions()["designer"].text
    assert "Fill `requested` in every `revise_package` call with each length with a unit" in text
    assert "quote the owner's own words" in text
    assert "is added to the value in the piece summary" in text
    assert "Use target `none` for a length that is not about the piece" in text
    assert "never invent a value" in text
