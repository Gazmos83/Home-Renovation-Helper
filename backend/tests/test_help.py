"""help-center: the help source loads, and a bad one stops startup by name."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.help import DEFAULT_HELP_PATH, HelpError, load_help, topic_text

TOPIC = "  - id: {id}\n    title: A topic\n    body:\n      - text: Some text.\n"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "help.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_shipped_help_loads_with_six_topics_in_order() -> None:
    assert load_help(DEFAULT_HELP_PATH).ids() == [
        "blueprint",
        "files",
        "template",
        "renders",
        "conversations",
        "workflow",
    ]


def test_template_topic_lists_six_steps_and_says_photo_sizes_are_estimates() -> None:
    template = load_help().topic("template")
    assert template is not None
    assert template.download == "import_template"
    steps = next(block for block in template.body if block.heading == "How to use the template")
    assert steps.items is not None and len(steps.items) == 6
    assert steps.items[0].startswith("Download the import template")
    assert steps.items[-1].startswith("Revise the imported piece")
    assert "estimates" in topic_text(template)


def test_default_prompt_asks_for_json_alone_in_millimetres_without_a_survey() -> None:
    template = load_help().topic("template")
    assert template is not None and template.prompt is not None
    prompt = template.prompt
    assert "JSON alone" in prompt
    assert "whole millimetres" in prompt
    assert "use only the fields it names" in prompt
    assert "do not add a room survey" in prompt


def test_blueprint_topic_keeps_the_measurements() -> None:
    blueprint = load_help().topic("blueprint")
    assert blueprint is not None
    text = topic_text(blueprint)
    for phrase in ("The ceiling height.", "The wall thickness.", "Every corner angle that is not 90°.", "scale reference"):
        assert phrase in text


def test_duplicate_topic_id_is_refused_by_name(tmp_path: Path) -> None:
    path = _write(tmp_path, "topics:\n" + TOPIC.format(id="template") + TOPIC.format(id="template"))
    with pytest.raises(HelpError, match=r"help\.yaml.*'template'"):
        load_help(path)


def test_unknown_field_is_refused_by_name(tmp_path: Path) -> None:
    path = _write(tmp_path, "topics:\n" + TOPIC.format(id="files") + "    colour: red\n")
    with pytest.raises(HelpError, match=r"help\.yaml.*colour"):
        load_help(path)


def test_block_with_text_and_items_is_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "topics:\n  - id: files\n    title: Files\n    body:\n      - text: A.\n        items: [B]\n",
    )
    with pytest.raises(HelpError, match="either text or items"):
        load_help(path)


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(HelpError, match="not found"):
        load_help(tmp_path / "help.yaml")
