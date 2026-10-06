"""cut-list-pricing: the Researcher's remnant tool — listing is free, changes wait for yes."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from app.agent.tools.base import Confirmation
from app.pricing import remnants
from plugins.material_cost.tool import preview_remnants, run_remnants
from tests.pricing_helpers import clean_pricing

ADD = {
    "action": "add", "material_key": "panel:oak-veneer-birch:18", "length_mm": 600, "width_mm": 400,
    "grain_axis": "length", "quantity": 2,
}


@pytest.fixture(autouse=True)
def clean(tool_state):
    clean_pricing(tool_state.engine)
    yield
    clean_pricing(tool_state.engine)


def rack(tool_deps) -> list:
    with tool_deps.session() as session:
        return remnants.list_remnants(session)


def test_listing_the_rack_needs_no_pause(make_ctx) -> None:
    assert preview_remnants({"action": "list"}, make_ctx()) is None
    assert run_remnants({"action": "list"}, make_ctx()) == "The remnant rack is empty."


def test_adding_pauses_and_the_rack_is_unchanged_until_yes(make_ctx, tool_deps) -> None:
    shown = preview_remnants(ADD, make_ctx())
    assert isinstance(shown, Confirmation) and shown.subject == "remnant"
    assert "2 × panel:oak-veneer-birch:18, 600 × 400 mm" in shown.summary
    assert "confirmation" in run_remnants(ADD, make_ctx())
    assert rack(tool_deps) == []

    done = run_remnants(ADD, replace(make_ctx(), approved=True))
    assert "Added to the rack: 2 ×" in done
    assert [(r.quantity, r.length_mm) for r in rack(tool_deps)] == [(2, 600)]
    assert "2 × panel:oak-veneer-birch:18" in run_remnants({"action": "list"}, make_ctx())


def test_removing_pauses_names_the_row_and_removes_only_on_yes(make_ctx, tool_deps) -> None:
    run_remnants(ADD, replace(make_ctx(), approved=True))
    remnant_id = str(rack(tool_deps)[0].id)
    shown = preview_remnants({"action": "remove", "remnant_id": remnant_id}, make_ctx())
    assert isinstance(shown, Confirmation) and "Remove from the remnant rack" in shown.summary
    assert len(rack(tool_deps)) == 1
    assert run_remnants({"action": "remove", "remnant_id": remnant_id}, replace(make_ctx(), approved=True)) == "Removed from the rack."
    assert rack(tool_deps) == []


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"action": "add"}, "give its material_key, length_mm, width_mm, grain_axis"),
        ({**ADD, "length_mm": 0}, "length and width must be positive"),
        ({"action": "remove"}, "give its remnant_id"),
        ({"action": "remove", "remnant_id": "00000000-0000-0000-0000-000000000000"}, "no remnant"),
        ({"action": "swap"}, "invalid arguments"),
    ],
)
def test_an_unusable_call_is_refused_with_no_pause(make_ctx, arguments, message) -> None:
    refused = preview_remnants(arguments, make_ctx())
    assert isinstance(refused, str) and message in refused


def test_pricing_never_changes_the_rack(make_ctx, tool_deps, tool_state) -> None:
    from sqlalchemy import text

    run_remnants(ADD, replace(make_ctx(), approved=True))
    before = [(r.id, r.quantity) for r in rack(tool_deps)]
    with Session(tool_state.engine) as session:
        session.execute(text("SELECT 1"))
    assert [(r.id, r.quantity) for r in rack(tool_deps)] == before
