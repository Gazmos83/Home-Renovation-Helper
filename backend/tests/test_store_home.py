"""cut-list-pricing: the one home store — capture, owner restrictions, cut classification."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.ingestion.fetcher import PacedFetcher
from app.pricing import store
from app.pricing.store import (
    CutGeometry,
    CutOutcome,
    CutSpec,
    DecidedBy,
    RestrictionKind,
    RestrictionValueError,
    UnknownStore,
    classify_cut,
    ingest_home_store,
    record_restriction,
)
from tests.pricing_helpers import clean_pricing

KEY = "berlin-friedrichshain"
STORE_HTML = """
<html><body>
<h1>toom Baumarkt in Berlin Friedrichshain</h1>
<p>Adresse: Hermann-Blankenstein-Str. 44, 10249 Berlin Märkte in der Nähe Bernau 16,9 km</p>
<p>Telefon 030 4677621-0</p>
<div class="service-tile"><a href="/service/services-im-markt/zuschnittservice/">Zuschnittservice</a></div>
<script>window.state = {"marketID": 3646};</script>
</body></html>
"""
STRAIGHT = CutSpec(geometry=CutGeometry.STRAIGHT, length_mm=2000, width_mm=600, thickness_mm=18, material="birch-ply")


@pytest.fixture
def session(migrated_database: str):
    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    clean_pricing(engine)
    with Session(engine) as s:
        yield s
        s.rollback()
    clean_pricing(engine)
    engine.dispose()


def fetcher(pages: dict[str, tuple[int, str]], robots: str = "User-agent: *\nAllow: /\n"):
    import httpx

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots, headers={"content-type": "text/plain"})
        status, body = pages.get(request.url.path, (404, "nope"))
        return httpx.Response(status, text=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PacedFetcher(user_agent="HomeRenovationAgentsBot/0.1 (+test)", min_interval_seconds=0, client=client), seen


def captured(session) -> None:
    f, _ = fetcher({f"/m/{KEY}/": (200, STORE_HTML)})
    with f:
        report = ingest_home_store(session, f, KEY)
    assert report.stores == 1, report.failures


def test_the_home_store_is_captured_with_its_cut_desk_and_market_id(session) -> None:
    captured(session)
    record = store.require_store(session, KEY)
    assert record.name == "Berlin Friedrichshain" and record.market_id == "3646"
    assert record.address.startswith("Hermann-Blankenstein-Str. 44")
    services = {s.service: s for s in store.store_services(session, KEY)}
    assert services["gerader_zuschnitt"].availability is store.ServiceAvailability.PERFORMED
    assert services["gerader_zuschnitt"].price_cents == 0 and services["gerader_zuschnitt"].is_free
    # Special cuts are priced nationally but their availability per market is not published.
    assert services["topfband_bohrung"].availability is store.ServiceAvailability.UNKNOWN
    assert services["topfband_bohrung"].price_cents == 299


def test_a_site_refusing_its_rules_is_reported_and_nothing_is_stored(session) -> None:
    import httpx

    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, text="denied")))
    f = PacedFetcher(user_agent="x", min_interval_seconds=0, client=client)
    with f:
        report = ingest_home_store(session, f, KEY)
    assert report.stores == 0 and "403" in report.failures[0]
    with pytest.raises(UnknownStore):
        store.require_store(session, KEY)


def test_a_page_the_rules_exclude_is_never_fetched(session) -> None:
    f, seen = fetcher({f"/m/{KEY}/": (200, STORE_HTML)}, robots="User-agent: *\nDisallow: /m/\n")
    with f:
        report = ingest_home_store(session, f, KEY)
    assert report.stores == 0 and "excluded" in report.failures[0]
    assert f"/m/{KEY}/" not in seen


def test_an_unknown_home_store_is_named_when_a_cut_is_classified(session) -> None:
    with pytest.raises(UnknownStore, match="berlin-friedrichshain"):
        classify_cut(session, KEY, STRAIGHT)


def test_a_straight_cut_is_covered_by_the_captured_cut_desk(session) -> None:
    captured(session)
    result = classify_cut(session, KEY, STRAIGHT)
    assert result.outcome is CutOutcome.COVERED
    assert (result.decided_by, result.price_cents) == (DecidedBy.CAPTURED_DATA, 0)


def test_a_cut_whose_availability_was_never_established_is_undetermined_not_refused(session) -> None:
    captured(session)
    mitre = CutSpec(geometry=CutGeometry.MITRE, length_mm=500, width_mm=500, thickness_mm=18)
    result = classify_cut(session, KEY, mitre)
    assert result.outcome is CutOutcome.UNDETERMINED and "has not been established" in result.reason


def test_an_owner_restriction_outranks_the_captured_service(session) -> None:
    captured(session)
    record_restriction(
        session, KEY, RestrictionKind.MAX_THICKNESS_MM, numeric_value=25, recorded_by="owner@example.com",
        note="the counter said so",
    )
    worktop = CutSpec(geometry=CutGeometry.STRAIGHT, length_mm=2000, width_mm=600, thickness_mm=27, material="oak")
    result = classify_cut(session, KEY, worktop)
    assert result.outcome is CutOutcome.CUSTOM
    assert result.decided_by is DecidedBy.OPERATOR_RECORD
    assert "above this store's recorded maximum of 25 mm" in result.reason
    # The same restriction does not touch a thin panel.
    assert classify_cut(session, KEY, STRAIGHT).outcome is CutOutcome.COVERED


def test_an_owner_record_can_settle_a_service_the_site_never_established(session) -> None:
    captured(session)
    record_restriction(
        session, KEY, RestrictionKind.PERMITTED_GEOMETRIES, text_value="straight, hinge_boring",
        recorded_by="owner@example.com",
    )
    boring = CutSpec(geometry=CutGeometry.HINGE_BORING, length_mm=500, width_mm=100, thickness_mm=18)
    result = classify_cut(session, KEY, boring)
    assert result.outcome is CutOutcome.COVERED and result.decided_by is DecidedBy.OPERATOR_RECORD
    mitre = CutSpec(geometry=CutGeometry.MITRE, length_mm=500, width_mm=500, thickness_mm=18)
    assert classify_cut(session, KEY, mitre).outcome is CutOutcome.CUSTOM


def test_a_limit_that_cannot_be_applied_is_undetermined(session) -> None:
    captured(session)
    record_restriction(
        session, KEY, RestrictionKind.MIN_FINISHED_DIMENSION_MM, numeric_value=100, recorded_by="owner@example.com"
    )
    result = classify_cut(session, KEY, CutSpec(geometry=CutGeometry.STRAIGHT, thickness_mm=18))
    assert result.outcome is CutOutcome.UNDETERMINED and "gives no finished dimensions" in result.reason


@pytest.mark.parametrize(
    ("kind", "kwargs", "message"),
    [
        (RestrictionKind.MAX_THICKNESS_MM, {}, "needs a numeric value"),
        (RestrictionKind.MAX_THICKNESS_MM, {"numeric_value": -5}, "positive measurement"),
        (RestrictionKind.PERMITTED_MATERIALS, {}, "comma-separated list"),
    ],
)
def test_a_restriction_that_cannot_be_applied_is_refused(session, kind, kwargs, message) -> None:
    captured(session)
    with pytest.raises(RestrictionValueError, match=message):
        record_restriction(session, KEY, kind, recorded_by="owner@example.com", **kwargs)


def test_restrictions_survive_a_recapture_and_can_be_deleted(session) -> None:
    captured(session)
    record_restriction(
        session, KEY, RestrictionKind.MAX_THICKNESS_MM, numeric_value=25, recorded_by="owner@example.com"
    )
    session.commit()
    captured(session)  # a re-run of the capture
    assert [r.restriction for r in store.store_restrictions(session, KEY)] == [RestrictionKind.MAX_THICKNESS_MM]
    assert store.delete_restriction(session, KEY, RestrictionKind.MAX_THICKNESS_MM) is True
    assert store.delete_restriction(session, KEY, RestrictionKind.MAX_THICKNESS_MM) is False
