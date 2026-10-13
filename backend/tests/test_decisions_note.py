"""chat-control-of-decisions: the row rules match the panel's (DecisionsNote.test.tsx)."""

from __future__ import annotations

import pytest

from app.agent.decisions_note import append_row, delete_row, replace_row, rows

NOTE = "# Decisions So Far\n\n## Figures\n- **Room:** Wohnen, **2500 mm** ceiling\n- doors: hinged\n\n## Doors\n- push-latch"


def test_rows_use_a_label_or_the_nearest_heading_and_drop_the_title() -> None:
    found = rows(NOTE)
    assert [(r.topic, r.decision) for r in found] == [
        ("Room", "Wohnen, 2500 mm ceiling"),
        ("Figures", "doors: hinged"),
        ("Doors", "push-latch"),
    ]
    assert [r.labelled for r in found] == [True, False, False]


def test_changing_a_decision_keeps_the_form_of_its_line() -> None:
    labelled, plain, _ = rows(NOTE)
    assert "- **Room:** Wohnen v2" in replace_row(NOTE, labelled, labelled.topic, "Wohnen v2")
    changed = replace_row(NOTE, plain, plain.topic, "doors: sliding")
    assert "- doors: sliding" in changed and changed.count("\n") == NOTE.count("\n")


def test_changing_the_topic_of_a_heading_row_writes_a_label() -> None:
    plain = rows("## Figures\n- ceiling 2500 mm")[0]
    assert replace_row("## Figures\n- ceiling 2500 mm", plain, "Height", "ceiling 2500 mm") == (
        "## Figures\n- **Height:** ceiling 2500 mm"
    )


def test_appending_a_row() -> None:
    assert append_row("## Figures\n- doors: hinged", "Handles", "push-latch") == (
        "## Figures\n- doors: hinged\n- **Handles:** push-latch"
    )
    assert append_row("", "Room", "Wohnen") == "- **Room:** Wohnen"
    assert append_row("- a\n\n", " Room ", "Wohnen\nv2") == "- a\n- **Room:** Wohnen v2"


def test_deleting_a_row_removes_a_heading_left_empty() -> None:
    text = "## Figures\n- **Room:** Wohnen\n## Doors\n- hinged"
    doors = rows(text)[1]
    assert delete_row(text, doors) == "## Figures\n- **Room:** Wohnen"
    room = rows(text)[0]
    assert delete_row(text, room) == "## Doors\n- hinged"


# --- drop-superseded-version-rows --------------------------------------------------------

from app.agent.decisions_note import superseded_version_rows

SAVED = "- **Version 1:** saved\n- v2 was created\n- Hall bench version 2 built"


def _dropped(text: str, approved: int = 4, others: list[tuple[str, str]] = ()) -> list[str]:
    return [r.decision for r in superseded_version_rows(text, "Hall bench", "hall-bench", approved, others)]


def test_bare_records_of_an_older_save_are_found() -> None:
    assert _dropped(SAVED) == ["saved", "v2 was created", "Hall bench version 2 built"]


@pytest.mark.parametrize(
    "row",
    [
        "- Version 2 had the doors on top; moved to the bottom",
        "- Version 2 saved because the owner liked it",
        "- Version 4 saved",
        "- Version 5 saved",
        "- Version 2 saved, version 4 approved",
        "- Doors on the bottom",
        "- Version 2 is wider",
    ],
)
def test_decisions_and_the_approved_or_newer_versions_are_kept(row: str) -> None:
    assert _dropped(row) == []


def test_another_pieces_row_is_kept_unless_it_names_this_piece() -> None:
    others = [("Listening wall", "listening-wall")]
    assert _dropped("- Listening wall version 1 saved", others=others) == []
    assert _dropped("- Hall bench and listening wall version 1 saved", others=others) != []
    assert _dropped("- Version 1 saved", others=others) != []
