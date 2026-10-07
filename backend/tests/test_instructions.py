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
    assert loaded["intake"].tools == ("record_brief", "record_plan")
    assert set(loaded["designer"].tools) == {
        "create_piece", "import_design", "revise_package", "cut_list", "room_fit", "search_guidelines",
    }
    assert set(loaded["builder"].tools) == {
        "blender_build", "build_shell", "render_turntable", "record_render_feedback",
    }
    assert loaded["reviewer"].tools == ("revision_review",)
    assert set(loaded["researcher"].tools) == {
        "search_catalog_knowledge", "check_live_listing", "compare_products", "price_cut_list", "manage_remnants",
    }


def test_the_designer_and_builder_never_offer_blender_code() -> None:
    loaded = load_instructions()
    for name in ("intake", "designer", "builder"):
        assert "Never offer to write Blender code" in loaded[name].text or "Never write, show or run Blender code" in loaded[name].text


def _break(tmp_path: Path, name: str, edit) -> str:
    directory = _copy(tmp_path)
    path = directory / f"{name}.md"
    path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(InstructionError) as error:
        load_instructions(directory)
    return str(error.value)


def test_an_unknown_tool_fails_naming_the_file(tmp_path: Path) -> None:
    message = _break(
        tmp_path, "designer", lambda text: text.replace("search_guidelines]", "search_guidelines, run_bpy]", 1)
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
