"""render-guard: tier required, raw knobs refused, estimate, approval, tickets."""

from __future__ import annotations

import pytest

from app.render.benchmark_store import Benchmark
from app.render.guard import (
    ApprovalRequired,
    RenderNotAuthorised,
    RenderRefused,
    RenderTicket,
    authorise,
    quote,
)
from app.render.tiers import load_tiers

TIERS = load_tiers()
BENCH = Benchmark(2.5, "2026-10-05T00:00:00+00:00", "5.2.1 LTS")


def _call(**overrides):
    args = {
        "package_id": "desk", "version": 1, "kind": "turntable", "tier": "draft",
        "tiers": TIERS, "benchmark": BENCH,
    }
    args.update(overrides)
    return authorise(**args)


def test_a_draft_turntable_is_authorised_with_its_estimate() -> None:
    ticket = _call()
    assert ticket.quote.tier.name == "draft"
    assert ticket.quote.frames == 12
    assert ticket.quote.estimate_seconds == pytest.approx(12 * 0.36 * 2.5)
    assert ticket.quote.estimate_text == "about 11 seconds"
    assert "tier draft" in ticket.quote.summary


def test_a_still_is_one_frame() -> None:
    ticket = _call(kind="still", tier="preview")
    assert ticket.quote.frames == 1
    assert ticket.quote.estimate_seconds == pytest.approx(1 * 1.0 * 2.5)
    assert "a still" in ticket.quote.summary


@pytest.mark.parametrize("tier", ["draft", "preview"])
def test_draft_and_preview_need_no_approval(tier: str) -> None:
    assert _call(tier=tier).quote.tier.name == tier


@pytest.mark.parametrize("tier", [None, ""])
def test_a_missing_tier_is_refused(tier) -> None:
    with pytest.raises(RenderRefused, match="tier is required") as caught:
        _call(tier=tier)
    assert caught.value.field == "tier"


def test_an_unknown_tier_is_refused_listing_the_three() -> None:
    with pytest.raises(RenderRefused) as caught:
        _call(tier="ultra")
    message = caught.value.reason
    assert "ultra" in message and all(t in message for t in ("draft", "preview", "final"))


@pytest.mark.parametrize("name", ["frames", "resolution", "width", "height", "samples", "engine"])
def test_a_raw_knob_is_refused_by_name(name: str) -> None:
    with pytest.raises(RenderRefused) as caught:
        _call(raw_fields=["tier", name])
    assert caught.value.field == name and name in caught.value.reason


def test_the_raw_knob_is_refused_before_anything_else() -> None:
    with pytest.raises(RenderRefused) as caught:
        _call(tier=None, benchmark=None, raw_fields=["engine"])
    assert caught.value.field == "engine"


def test_no_benchmark_is_refused_with_the_reason() -> None:
    with pytest.raises(RenderRefused, match="benchmark first") as caught:
        _call(benchmark=None)
    assert caught.value.failure_class == "benchmark_missing"


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(RenderRefused, match="kind"):
        _call(kind="video")


def test_a_final_without_approval_asks_with_the_estimate() -> None:
    with pytest.raises(ApprovalRequired) as caught:
        _call(tier="final")
    assert caught.value.quote.estimate_seconds == pytest.approx(36 * 2.25 * 30 * 2.5)
    assert "about 101 minutes" in caught.value.reason
    assert caught.value.failure_class == "approval_required"


def test_a_final_uses_the_calibrated_multiplier() -> None:
    q = quote(
        package_id="d", version=1, kind="turntable", tier="final", tiers=TIERS,
        benchmark=BENCH, cycles_multiplier=10,
    )
    assert q.estimate_seconds == pytest.approx(36 * 2.25 * 10 * 2.5)


@pytest.mark.parametrize("answer", ["yes", "Yes", " YES "])
def test_a_final_with_yes_is_authorised(answer: str) -> None:
    assert _call(tier="final", approval=answer).quote.tier.name == "final"


@pytest.mark.parametrize("answer", ["no", "y", "yes please", "", True, 1])
def test_anything_but_yes_declines_a_final(answer) -> None:
    with pytest.raises(RenderRefused) as caught:
        _call(tier="final", approval=answer)
    assert caught.value.failure_class == "declined"
    assert not isinstance(caught.value, ApprovalRequired)


def test_a_ticket_is_single_use_and_reports_consumed() -> None:
    ticket = _call()
    assert ticket.consumed is False
    ticket.consume()
    assert ticket.consumed is True
    with pytest.raises(RenderNotAuthorised, match="already used"):
        ticket.consume()


def test_a_ticket_matches_only_its_own_request() -> None:
    ticket = _call(room=True)
    assert ticket.matches("desk", 1, "turntable", True)
    assert not ticket.matches("desk", 2, "turntable", True)
    assert not ticket.matches("other", 1, "turntable", True)
    assert not ticket.matches("desk", 1, "still", True)
    assert not ticket.matches("desk", 1, "turntable", False)


def test_a_ticket_cannot_be_constructed_outside_the_guard() -> None:
    q = _call().quote
    with pytest.raises(RenderNotAuthorised):
        RenderTicket(q)
    with pytest.raises(RenderNotAuthorised):
        RenderTicket(q, _mint=object())


# --- detail renders (photoreal-detail) ------------------------------------------------------------


@pytest.mark.parametrize("tier", ["draft", "preview"])
def test_a_detail_render_below_final_is_refused(tier: str) -> None:
    with pytest.raises(RenderRefused, match="final only") as caught:
        _call(tier=tier, source="detail", approval="yes")
    assert caught.value.field == "tier"


def test_a_detail_render_in_a_room_is_refused() -> None:
    with pytest.raises(RenderRefused, match="piece alone") as caught:
        _call(tier="final", source="detail", room=True, approval="yes")
    assert caught.value.field == "room"


def test_a_detail_final_asks_with_the_cycles_estimate_then_runs_on_yes() -> None:
    with pytest.raises(ApprovalRequired) as asked:
        _call(tier="final", source="detail")
    quoted = asked.value.quote
    assert (quoted.frames, quoted.tier.resolution, quoted.tier.engine) == (36, 1500, "cycles")
    assert quoted.source == "detail" and "detailed copy" in quoted.summary
    assert _call(tier="final", source="detail", approval="yes").quote.source == "detail"


def test_an_unknown_source_is_refused_by_name() -> None:
    with pytest.raises(RenderRefused) as caught:
        _call(source="other")
    assert caught.value.field == "source"


def test_a_ticket_for_the_model_does_not_match_the_detail_copy_nor_the_reverse() -> None:
    model = _call(tier="final", approval="yes")
    detail = _call(tier="final", source="detail", approval="yes")
    assert model.matches("desk", 1, "turntable", False, "piece", "model")
    assert not model.matches("desk", 1, "turntable", False, "piece", "detail")
    assert detail.matches("desk", 1, "turntable", False, "piece", "detail")
    assert not detail.matches("desk", 1, "turntable", False, "piece", "model")
    assert not detail.matches("desk", 1, "turntable", False)


# --- restyle renders (restyle-variants) ------------------------------------------------------------


def test_a_restyle_at_final_is_refused_as_a_concept_picture() -> None:
    with pytest.raises(RenderRefused, match="concept picture") as caught:
        _call(kind="still", tier="final", source="restyle", variant="walnut-draft", approval="yes")
    assert caught.value.field == "tier"


@pytest.mark.parametrize("tier", ["draft", "preview"])
def test_a_restyle_at_draft_or_preview_needs_no_approval_and_is_one_frame(tier: str) -> None:
    ticket = _call(kind="still", tier=tier, source="restyle", variant="walnut")
    assert ticket.quote.source == "restyle" and ticket.quote.frames == 1
    assert "restyle" in ticket.quote.summary


def test_a_restyle_is_a_still_for_a_named_variant_on_the_laptop() -> None:
    with pytest.raises(RenderRefused, match="still"):
        _call(kind="turntable", source="restyle", variant="walnut")
    with pytest.raises(RenderRefused, match="named variant"):
        _call(kind="still", source="restyle")


def test_a_restyle_batch_estimate_is_the_sum_of_single_frame_estimates() -> None:
    quotes = [
        quote(package_id="desk", version=1, kind="still", tier="draft", tiers=TIERS, benchmark=BENCH,
              source="restyle", variant=name)
        for name in ("walnut", "oak", "sage-green")
    ]
    single = quote(package_id="desk", version=1, kind="still", tier="draft", tiers=TIERS, benchmark=BENCH)
    assert sum(q.estimate_seconds for q in quotes) == pytest.approx(3 * single.estimate_seconds)


def test_a_ticket_for_one_variant_does_not_match_another_nor_the_built_model() -> None:
    ticket = _call(kind="still", source="restyle", variant="walnut")
    assert ticket.matches("desk", 1, "still", False, "piece", "restyle", "walnut")
    assert not ticket.matches("desk", 1, "still", False, "piece", "restyle", "sage-green")
    assert not ticket.matches("desk", 1, "still", False, "piece", "model")
    model = _call(kind="still")
    assert not model.matches("desk", 1, "still", False, "piece", "restyle", "walnut")
