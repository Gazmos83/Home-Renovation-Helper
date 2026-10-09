"""design-agents: the owner's requested measurements, checked by code (app-check-2026-10-09)."""

from __future__ import annotations

import copy

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.measurements import Requested, check, lengths, owner_texts_since_version

CURRENT = {
    "modules": [{"id": "cabinet", "x": 0, "y": 0, "z": 0, "width": 600, "height": 2238, "depth": 400}],
    "envelope": {"width": 2206, "height": 2238, "depth": 400},
}


def revised(**fields) -> dict:
    document = copy.deepcopy(CURRENT)
    document["modules"][0].update(fields)
    return document


@pytest.mark.parametrize(
    ("text", "mm", "relative", "sign"),
    [
        ("make it 80 cm wide", 800, False, 0),
        ("0,8 m wide", 800, False, 0),
        ("800mm", 800, False, 0),
        ("5 cm wider", 50, True, 1),
        ("2 cm less deep", 20, True, -1),
        ("make it narrower by 3 cm", 30, True, -1),
        ("change the depth by 3 cm", 30, True, 0),
    ],
)
def test_lengths_are_read_in_millimetres(text: str, mm: float, relative: bool, sign: int) -> None:
    [found] = lengths(text)
    assert (found.mm, found.relative, found.sign) == (mm, relative, sign)


def test_text_without_a_unit_has_no_length() -> None:
    assert lengths("3 shelves and 2 doors, about 1200 wide") == []


def test_an_absolute_width_honoured_passes() -> None:
    entry = Requested("make the cabinet 80 cm wide", "cabinet", "width", 800)
    assert check([entry], ["make the cabinet 80 cm wide"], CURRENT, revised(width=800)) == []


def test_an_invented_value_is_refused_naming_quote_expected_and_set() -> None:
    entry = Requested("80 cm wide", "cabinet", "width", 800)
    [refusal] = check([entry], ["make the cabinet 80 cm wide"], CURRENT, revised(width=750))
    assert "'80 cm wide'" in refusal and "800 mm expected" in refusal and "set 750 mm" in refusal


def test_an_entry_with_the_wrong_value_is_refused() -> None:
    entry = Requested("80 cm wide", "cabinet", "width", 750)
    refusal, uncovered = check([entry], ["make the cabinet 80 cm wide"], CURRENT, revised(width=750))
    assert "'80 cm wide' gives cabinet width 800 mm, not 750 mm" in refusal
    assert "'80 cm' is not covered" in uncovered


def test_a_relative_change_is_resolved_against_the_latest_version() -> None:
    entry = Requested("5 cm wider", "cabinet", "width", 650)
    assert check([entry], ["make the cabinet 5 cm wider"], CURRENT, revised(width=650)) == []


def test_a_relative_change_to_the_envelope_is_resolved() -> None:
    entry = Requested("2 cm less deep", "envelope", "depth", 380)
    changed = copy.deepcopy(CURRENT) | {"envelope": {"width": 2206, "height": 2238, "depth": 380}}
    assert check([entry], ["the whole wall 2 cm less deep"], CURRENT, changed) == []


def test_a_measurement_left_out_is_refused_as_not_covered() -> None:
    entry = Requested("80 cm wide", "cabinet", "width", 800)
    refusals = check([entry], ["80 cm wide and 40 cm deep"], CURRENT, revised(width=800, depth=400))
    assert refusals == [
        "the owner's '40 cm' is not covered: add it to `requested` (target `none` when it is not about the piece)"
    ]


def test_an_empty_list_fails_when_the_owner_gave_a_length() -> None:
    assert check([], ["make it 80 cm wide"], CURRENT, revised(width=800))


def test_a_quote_not_from_the_owner_is_refused() -> None:
    entry = Requested("90 cm", "cabinet", "width", 900)
    [refusal] = check([entry], ["make it wider"], CURRENT, revised(width=900))
    assert refusal.startswith("'90 cm' is not in the owner's messages")


def test_a_length_not_about_the_piece_is_covered_by_a_none_entry() -> None:
    said = ["the room is 4 m wide, make the cabinet 80 cm wide"]
    entries = [
        Requested("80 cm wide", "cabinet", "width", 800),
        Requested("4 m wide", "none", "", 0),
    ]
    assert check(entries, said, CURRENT, revised(width=800)) == []


def test_a_none_entry_still_needs_its_quote() -> None:
    [refusal] = check([Requested("4 m wide", "none", "", 0)], ["make it wider"], CURRENT, CURRENT)
    assert "not in the owner's messages" in refusal


def test_an_unknown_field_is_refused_naming_it() -> None:
    refusals = check([Requested("80 cm", "cabinet", "colour", 800)], ["80 cm"], CURRENT, CURRENT)
    assert "cabinet has no length field 'colour'" in refusals[0]


def test_text_with_no_unit_needs_no_entry() -> None:
    assert check([], ["add 3 shelves"], CURRENT, CURRENT) == []


def _created(call_id: str, text: str, name: str = "revise_package") -> list:
    return [
        AIMessage("", tool_calls=[{"id": call_id, "name": name, "args": {}}]),
        ToolMessage(text, tool_call_id=call_id),
    ]


def test_only_the_owners_messages_after_the_last_created_version_count() -> None:
    history = [
        HumanMessage("a bench 120 cm wide"),
        *_created("a", "Created bench version 1; the build has started.", "create_piece"),
        HumanMessage("make it 5 cm wider"),
        *_created("b", "Created bench version 2 (revised from 1): bench: width 1200 → 1250."),
        AIMessage("Done."),
        HumanMessage("now 40 cm deep"),
    ]
    assert owner_texts_since_version(history, "bench") == ["now 40 cm deep"]
    assert owner_texts_since_version(history, "shelf") == [
        "a bench 120 cm wide", "make it 5 cm wider", "now 40 cm deep",
    ]


def test_a_composition_result_does_not_start_a_window() -> None:
    history = [
        HumanMessage("80 cm wide"),
        *_created("c", "Created bench version 3; its build has started.", "compose_room"),
    ]
    assert owner_texts_since_version(history, "bench") == ["80 cm wide"]


# --- shelf spacing and divider positions (shelf-spacing-and-dividers) ------------------------

SAID = "4 shelves 355 mm apart"


def test_a_spacing_on_a_module_that_had_none_passes() -> None:
    entry = Requested(SAID, "cabinet", "shelf_spacing_mm", 355)
    assert check([entry], [SAID], CURRENT, revised(shelf_spacing_mm=355)) == []


def test_an_invented_spacing_is_refused() -> None:
    entry = Requested("355 mm apart", "cabinet", "shelf_spacing_mm", 355)
    [refusal] = check([entry], [SAID], CURRENT, revised(shelf_spacing_mm=373))
    assert "'355 mm apart'" in refusal and "355 mm expected" in refusal and "set 373 mm" in refusal
    wrong = Requested("355 mm apart", "cabinet", "shelf_spacing_mm", 373)
    assert "gives cabinet shelf_spacing_mm 355 mm, not 373 mm" in check([wrong], [SAID], CURRENT, revised())[0]


def test_a_relative_length_on_an_unset_field_is_refused() -> None:
    entry = Requested("5 cm more", "cabinet", "shelf_spacing_mm", 50)
    refusal, uncovered = check([entry], ["5 cm more between the shelves"], CURRENT, revised(shelf_spacing_mm=50))
    assert "not set in the latest version" in refusal and "'5 cm' is not covered" in uncovered


def test_a_divider_position_is_found_in_the_revised_list() -> None:
    said = "a divider 400 mm from the left"
    entry = Requested(said, "cabinet", "divider_positions_mm", 400)
    assert check([entry], [said], CURRENT, revised(dividers=1, divider_positions_mm=[400])) == []
    [refusal] = check([entry], [said], CURRENT, revised(dividers=1, divider_positions_mm=[450]))
    assert "400 mm expected" in refusal and "[450 mm]" in refusal


def test_each_listed_position_needs_its_own_entry() -> None:
    said = "shelves at 300 mm and 700 mm"
    entry = Requested("300 mm", "cabinet", "shelf_positions_mm", 300)
    [uncovered] = check([entry], [said], CURRENT, revised(shelf_positions_mm=[300, 700]))
    assert "'700 mm' is not covered" in uncovered
    second = Requested("700 mm", "cabinet", "shelf_positions_mm", 700)
    assert check([entry, second], [said], CURRENT, revised(shelf_positions_mm=[300, 700])) == []


def test_an_unknown_field_on_an_unset_module_value_is_still_refused() -> None:
    entry = Requested(SAID, "cabinet", "shelf_gap", 355)
    assert "has no length field 'shelf_gap'" in check([entry], [SAID], CURRENT, revised())[0]
