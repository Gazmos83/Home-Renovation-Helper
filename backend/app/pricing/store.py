"""The home toom store: what it offers, what the owner established on site, and what a cut needs.

Two kinds of knowledge with different standing. What toom publishes (the cut
desk, the national service prices) is captured with a source URL and a time. What
the owner established by phoning or visiting is recorded by them and outranks the
pages, because a limit learned at the counter reflects the store as it is rather
than as advertised. Where they disagree the owner's record decides, and every
answer says which source decided it. A missing record is never a negative answer:
"not established" and "the store does not do this" are kept apart throughout.

One home store only (`TOOM_HOME_STORE`); the predecessor's whole-directory
capture, distances and nearby-store ranking are not carried over.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Store, StoreCutRestriction, StoreService
from app.ingestion.extract import visible_text
from app.ingestion.fetcher import PacedFetcher
from app.ingestion.robots import RULES_PATH, RulesUnavailable

logger = logging.getLogger(__name__)

TOOM_BASE = "https://toom.de"


class ServiceAvailability(StrEnum):
    """Whether a store performs a service, with 'not established' kept distinct."""

    PERFORMED = "performed"
    NOT_PERFORMED = "not_performed"
    UNKNOWN = "unknown"


class RestrictionKind(StrEnum):
    """The limits that decide whether a cut has to be sourced elsewhere."""

    MIN_FINISHED_DIMENSION_MM = "min_finished_dimension_mm"
    MAX_WORKABLE_DIMENSION_MM = "max_workable_dimension_mm"
    MAX_THICKNESS_MM = "max_thickness_mm"
    PERMITTED_GEOMETRIES = "permitted_geometries"
    PERMITTED_MATERIALS = "permitted_materials"


class UnknownStore(Exception):
    """Named a store the directory does not hold."""

    def __init__(self, store_key: str) -> None:
        self.store_key = store_key
        super().__init__(
            f"the home store {store_key!r} has not been captured; run "
            "`python -m app.ingestion --store` or correct TOOM_HOME_STORE"
        )


class RestrictionValueError(Exception):
    """A restriction was submitted with a value that cannot be applied."""


# --- cut vocabulary ----------------------------------------------------------


class CutGeometry(StrEnum):
    """The shapes of cut a store may or may not perform."""

    STRAIGHT = "straight"
    MITRE = "mitre"
    CUTOUT = "cutout"
    HOLE = "hole"
    HINGE_BORING = "hinge_boring"
    CORNER_JOINT = "corner_joint"


# toom's own service names, as published on the Zuschnittservice page.
SERVICE_FOR_GEOMETRY: dict[CutGeometry, str] = {
    CutGeometry.STRAIGHT: "gerader_zuschnitt",
    CutGeometry.MITRE: "kapp_und_gehrungsschnitt",
    CutGeometry.CUTOUT: "spuelen_und_herdausschnitt",
    CutGeometry.HOLE: "spuelenlochstanzung",
    CutGeometry.HINGE_BORING: "topfband_bohrung",
    CutGeometry.CORNER_JOINT: "professionelle_eckverbindung",
}


class CutOutcome(StrEnum):
    COVERED = "covered"
    CUSTOM = "custom"
    UNDETERMINED = "undetermined"


class DecidedBy(StrEnum):
    OPERATOR_RECORD = "operator_record"
    CAPTURED_DATA = "captured_data"


@dataclass(frozen=True, slots=True)
class CutSpec:
    """A cut someone needs made, in the terms a store would understand."""

    geometry: CutGeometry
    length_mm: float | None = None
    width_mm: float | None = None
    thickness_mm: float | None = None
    material: str | None = None

    @property
    def smallest_finished_dimension(self) -> float | None:
        known = [d for d in (self.length_mm, self.width_mm) if d is not None]
        return min(known) if known else None

    @property
    def largest_finished_dimension(self) -> float | None:
        known = [d for d in (self.length_mm, self.width_mm) if d is not None]
        return max(known) if known else None


@dataclass(frozen=True, slots=True)
class Classification:
    """Whether a store can make a cut, and what settled it."""

    outcome: CutOutcome
    reason: str
    store_key: str
    service: str
    decided_by: DecidedBy | None = None
    price_cents: int | None = None
    restriction: str | None = None
    restriction_value: float | str | None = None

    @property
    def requires_custom_work(self) -> bool:
        return self.outcome is CutOutcome.CUSTOM


@dataclass(frozen=True, slots=True)
class StoreRecord:
    store_key: str
    name: str
    address: str | None
    phone: str | None
    url: str
    captured_at: datetime
    # The retailer's own identifier for this store, where published (day 4:
    # live-listing-lookup). `None` is reported as such, never defaulted.
    market_id: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceRecord:
    service: str
    availability: ServiceAvailability
    price_cents: int | None
    url: str
    captured_at: datetime

    @property
    def price_is_known(self) -> bool:
        return self.price_cents is not None

    @property
    def is_free(self) -> bool:
        """Free is not the same as unpriced, and must not read as unknown."""
        return self.price_cents == 0


@dataclass(frozen=True, slots=True)
class RestrictionRecord:
    restriction: RestrictionKind
    numeric_value: float | None
    text_value: str | None
    recorded_by: str
    recorded_at: datetime
    note: str | None = None

    @property
    def permitted_values(self) -> list[str]:
        if not self.text_value:
            return []
        return [item.strip().lower() for item in self.text_value.split(",") if item.strip()]


def get_store(session: Session, store_key: str) -> StoreRecord | None:
    row = session.get(Store, store_key)
    if row is None:
        return None
    return StoreRecord(
        store_key=row.store_key,
        name=row.name,
        address=row.address,
        phone=row.phone,
        url=row.url,
        captured_at=row.captured_at,
        market_id=row.market_id,
    )


def require_store(session: Session, store_key: str) -> StoreRecord:
    record = get_store(session, store_key)
    if record is None:
        raise UnknownStore(store_key)
    return record


def store_services(session: Session, store_key: str) -> list[ServiceRecord]:
    require_store(session, store_key)
    rows = session.execute(
        select(StoreService)
        .where(StoreService.store_key == store_key)
        .order_by(StoreService.service)
    ).scalars()
    return [
        ServiceRecord(
            service=row.service,
            availability=ServiceAvailability(row.availability),
            price_cents=row.price_cents,
            url=row.url,
            captured_at=row.captured_at,
        )
        for row in rows
    ]


def find_service(
    session: Session, store_key: str, service: str
) -> ServiceRecord | None:
    return next(
        (record for record in store_services(session, store_key) if record.service == service),
        None,
    )


# --- operator records --------------------------------------------------------


def store_restrictions(session: Session, store_key: str) -> list[RestrictionRecord]:
    require_store(session, store_key)
    rows = session.execute(
        select(StoreCutRestriction)
        .where(StoreCutRestriction.store_key == store_key)
        .order_by(StoreCutRestriction.restriction)
    ).scalars()
    return [
        RestrictionRecord(
            restriction=RestrictionKind(row.restriction),
            numeric_value=row.numeric_value,
            text_value=row.text_value,
            recorded_by=row.recorded_by,
            recorded_at=row.recorded_at,
            note=row.note,
        )
        for row in rows
    ]


NUMERIC_RESTRICTIONS = {
    RestrictionKind.MIN_FINISHED_DIMENSION_MM,
    RestrictionKind.MAX_WORKABLE_DIMENSION_MM,
    RestrictionKind.MAX_THICKNESS_MM,
}


def record_restriction(
    session: Session,
    store_key: str,
    restriction: RestrictionKind,
    *,
    numeric_value: float | None = None,
    text_value: str | None = None,
    recorded_by: str,
    note: str | None = None,
) -> RestrictionRecord:
    """Record, or revise, a limit established on site.

    Validated before it is stored: a restriction that cannot be applied would
    otherwise sit in the directory looking authoritative while silently never
    affecting a classification.
    """
    require_store(session, store_key)

    if not recorded_by or not recorded_by.strip():
        raise RestrictionValueError("a restriction must record who established it")

    if restriction in NUMERIC_RESTRICTIONS:
        if numeric_value is None:
            raise RestrictionValueError(
                f"{restriction.value} is a measurement and needs a numeric value"
            )
        if numeric_value <= 0:
            raise RestrictionValueError(
                f"{restriction.value} must be a positive measurement in millimetres, "
                f"got {numeric_value}"
            )
        text_value = None
    else:
        if not text_value or not text_value.strip():
            raise RestrictionValueError(
                f"{restriction.value} needs a comma-separated list of permitted values"
            )
        numeric_value = None

    recorded_at = datetime.now(UTC)
    statement = (
        insert(StoreCutRestriction)
        .values(
            store_key=store_key,
            restriction=restriction.value,
            numeric_value=numeric_value,
            text_value=text_value,
            recorded_by=recorded_by.strip(),
            recorded_at=recorded_at,
            note=note,
        )
        .on_conflict_do_update(
            constraint="uq_store_cut_restriction",
            set_={
                "numeric_value": numeric_value,
                "text_value": text_value,
                "recorded_by": recorded_by.strip(),
                "recorded_at": recorded_at,
                "note": note,
            },
        )
    )
    session.execute(statement)

    return RestrictionRecord(
        restriction=restriction,
        numeric_value=numeric_value,
        text_value=text_value,
        recorded_by=recorded_by.strip(),
        recorded_at=recorded_at,
        note=note,
    )


# --- classification ----------------------------------------------------------


def _breached_restriction(
    spec: CutSpec, restrictions: Sequence[RestrictionRecord]
) -> tuple[RestrictionRecord, str] | None:
    """The first recorded limit this cut falls outside, if any."""
    for record in restrictions:
        kind = record.restriction

        if kind is RestrictionKind.MIN_FINISHED_DIMENSION_MM:
            smallest = spec.smallest_finished_dimension
            if smallest is not None and record.numeric_value is not None and smallest < record.numeric_value:
                return record, (
                    f"the finished piece measures {smallest:g} mm, below this "
                    f"store's recorded minimum of {record.numeric_value:g} mm"
                )

        elif kind is RestrictionKind.MAX_WORKABLE_DIMENSION_MM:
            largest = spec.largest_finished_dimension
            if largest is not None and record.numeric_value is not None and largest > record.numeric_value:
                return record, (
                    f"the piece measures {largest:g} mm, above this store's "
                    f"recorded maximum of {record.numeric_value:g} mm"
                )

        elif kind is RestrictionKind.MAX_THICKNESS_MM:
            if (
                spec.thickness_mm is not None
                and record.numeric_value is not None
                and spec.thickness_mm > record.numeric_value
            ):
                return record, (
                    f"the material is {spec.thickness_mm:g} mm thick, above this "
                    f"store's recorded maximum of {record.numeric_value:g} mm"
                )

        elif kind is RestrictionKind.PERMITTED_GEOMETRIES:
            permitted = record.permitted_values
            if permitted and spec.geometry.value not in permitted:
                return record, (
                    f"this store is recorded as performing only "
                    f"{', '.join(permitted)} cuts, not {spec.geometry.value}"
                )

        elif kind is RestrictionKind.PERMITTED_MATERIALS:
            permitted = record.permitted_values
            if permitted and spec.material and spec.material.lower() not in permitted:
                return record, (
                    f"this store is recorded as cutting only {', '.join(permitted)}, "
                    f"not {spec.material}"
                )

    return None


def _missing_input(
    spec: CutSpec, restrictions: Sequence[RestrictionRecord]
) -> str | None:
    """A recorded limit that cannot be applied because the cut does not say enough."""
    for record in restrictions:
        kind = record.restriction
        if (
            kind
            in {
                RestrictionKind.MIN_FINISHED_DIMENSION_MM,
                RestrictionKind.MAX_WORKABLE_DIMENSION_MM,
            }
            and spec.smallest_finished_dimension is None
        ):
            return "the cut gives no finished dimensions, which this store limits"
        if kind is RestrictionKind.MAX_THICKNESS_MM and spec.thickness_mm is None:
            return "the cut gives no material thickness, which this store limits"
        if kind is RestrictionKind.PERMITTED_MATERIALS and spec.material is None:
            return "the cut names no material, and this store limits which it cuts"
    return None


def classify_cut(session: Session, store_key: str, spec: CutSpec) -> Classification:
    """Whether `store_key` can make `spec`, and on whose authority.

    Operator records outrank captured page data in both directions: they can
    rule out a cut the site advertises, and they can settle one the site never
    established.
    """
    require_store(session, store_key)
    service = SERVICE_FOR_GEOMETRY[spec.geometry]
    restrictions = store_restrictions(session, store_key)

    breach = _breached_restriction(spec, restrictions)
    if breach is not None:
        record, reason = breach
        return Classification(
            outcome=CutOutcome.CUSTOM,
            reason=reason,
            store_key=store_key,
            service=service,
            decided_by=DecidedBy.OPERATOR_RECORD,
            restriction=record.restriction.value,
            restriction_value=(
                record.numeric_value if record.numeric_value is not None else record.text_value
            ),
        )

    missing = _missing_input(spec, restrictions)
    if missing is not None:
        return Classification(
            outcome=CutOutcome.UNDETERMINED,
            reason=missing,
            store_key=store_key,
            service=service,
            decided_by=DecidedBy.OPERATOR_RECORD,
        )

    # An operator listing the permitted geometries settles availability even
    # where the captured pages never established it.
    geometry_record = next(
        (r for r in restrictions if r.restriction is RestrictionKind.PERMITTED_GEOMETRIES),
        None,
    )
    captured = find_service(session, store_key, service)

    if geometry_record is not None and spec.geometry.value in geometry_record.permitted_values:
        return Classification(
            outcome=CutOutcome.COVERED,
            reason=(
                f"recorded on site by {geometry_record.recorded_by} as a cut this "
                f"store performs"
            ),
            store_key=store_key,
            service=service,
            decided_by=DecidedBy.OPERATOR_RECORD,
            price_cents=captured.price_cents if captured else None,
        )

    if captured is None:
        return Classification(
            outcome=CutOutcome.UNDETERMINED,
            reason=(
                f"no record of whether this store performs {service}; record it "
                f"from the store to settle this"
            ),
            store_key=store_key,
            service=service,
        )

    if captured.availability is ServiceAvailability.NOT_PERFORMED:
        return Classification(
            outcome=CutOutcome.CUSTOM,
            reason=f"this store does not perform {service}",
            store_key=store_key,
            service=service,
            decided_by=DecidedBy.CAPTURED_DATA,
        )

    if captured.availability is ServiceAvailability.UNKNOWN:
        return Classification(
            outcome=CutOutcome.UNDETERMINED,
            reason=(
                f"whether this store performs {service} has not been established; "
                f"contact the store to confirm"
            ),
            store_key=store_key,
            service=service,
            decided_by=DecidedBy.CAPTURED_DATA,
        )

    return Classification(
        outcome=CutOutcome.COVERED,
        reason=f"this store performs {service}",
        store_key=store_key,
        service=service,
        decided_by=DecidedBy.CAPTURED_DATA,
        price_cents=captured.price_cents,
    )


# --- capturing the home store ------------------------------------------------

_STORE_KEY = re.compile(r"/m/([a-z0-9-]+)/?$", re.IGNORECASE)
_ADDRESS = re.compile(r"Adresse\s*:?\s*(.{5,120}?)(?:Märkte in der Nähe|$)", re.DOTALL)
# No `\s`: it matches newlines, so an opening-hours line ending in "08:00"
# would run into the phone number on the next line and be captured with it.
_PHONE = re.compile(r"(0\d[\d /-]{6,20}\d)")
# A store that runs a cut desk carries the service in its own service tiles —
# a `Zuschnittservice` icon and a link to it. Verified as a per-store signal,
# not global chrome: it appears 14 times on the Friedrichshain store page and
# not at all on toom's delivery or category pages. Matched against the raw
# markup because the tile lives in a region the corpus extractor drops.
_CUT_DESK = re.compile(r"zuschnittservice", re.IGNORECASE)

# The retailer's own identifier for this store, embedded in the page's client
# state rather than rendered as visible text (probed 2026-09-17: Berlin-
# Friedrichshain's page embeds `marketID … 3646`). Matched against the raw
# markup for the same reason as the cut desk signal. Not every store page
# publishes one, and a page that does not must not be assumed to be the
# default market (live-listing-lookup §"store scoping").
_MARKET_ID = re.compile(r'"?marketID"?\s*[:=]\s*"?(\d+)"?', re.IGNORECASE)

# Prices as published nationally on the Zuschnittservice page, in cents.
# A straight cut is "i.d.R. kostenlos" — free, which is a price, not an
# absence of one, and the store is charged 0 rather than left null.
NATIONAL_CUT_PRICES: dict[str, int] = {
    "gerader_zuschnitt": 0,
    "topfband_bohrung": 299,
    "spuelenlochstanzung": 499,
    "kapp_und_gehrungsschnitt": 799,
    "fraesung_arbeitsplattenverbinder": 999,
    "spuelen_und_herdausschnitt": 1299,
    "professionelle_eckverbindung": 2499,
}

CUT_SERVICE_URL = "https://toom.de/service/services-im-markt/zuschnittservice/"

# The stores a Berlin project can realistically reach. toom runs 294 markets
# nationally; capturing all of them would cost 294 requests to answer questions
# that only ever concern this region.
BERLIN_BRANDENBURG: list[str] = [
    "berlin-friedrichshain",
    "berlin-weissensee",
    "bernau",
    "brandenburg-havel",
    "cottbus",
    "eberswalde",
    "frankfurt-oder",
    "frankfurt-oder-west",
    "fuerstenwalde",
    "fuerstenwalde-2",
    "luckenwalde",
    "potsdam-babelsberg",
    "stahnsdorf",
]


@dataclass
class StoreCapture:
    store_key: str
    name: str
    url: str
    address: str | None = None
    phone: str | None = None
    offers_cutting: bool = False
    market_id: str | None = None


@dataclass
class StoreRunReport:
    stores: int = 0
    services: int = 0
    failures: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"home store: {self.stores} captured, {self.services} service records, {len(self.failures)} failed"


def store_key_from_url(url: str) -> str | None:
    match = _STORE_KEY.search(url)
    return match.group(1).lower() if match else None


def parse_store_page(url: str, html: str) -> StoreCapture:
    """Pull identity, address, phone, market id and whether the store shows a cut desk."""
    key = store_key_from_url(url) or url
    text = visible_text(html)

    name = key.replace("-", " ").title()
    heading = re.search(r"toom Baumarkt in ([^\n]{3,60})", text)
    if heading:
        name = heading.group(1).strip()

    address = None
    address_match = _ADDRESS.search(text)
    if address_match:
        address = " ".join(address_match.group(1).split())[:200]

    phone_match = _PHONE.search(text)
    phone = phone_match.group(1).strip() if phone_match else None

    market_id_match = _MARKET_ID.search(html)
    market_id = market_id_match.group(1) if market_id_match else None

    return StoreCapture(
        store_key=key,
        name=name,
        url=url,
        address=address,
        phone=phone,
        offers_cutting=bool(_CUT_DESK.search(html)),
        market_id=market_id,
    )




NATIONAL_CUT_PRICES: dict[str, int] = {
    "gerader_zuschnitt": 0,
    "topfband_bohrung": 299,
    "spuelenlochstanzung": 499,
    "kapp_und_gehrungsschnitt": 799,
    "fraesung_arbeitsplattenverbinder": 999,
    "spuelen_und_herdausschnitt": 1299,
    "professionelle_eckverbindung": 2499,
}
CUT_SERVICE_URL = "https://toom.de/service/services-im-markt/zuschnittservice/"


def upsert_store(session: Session, capture: StoreCapture, *, source_site: str = "toom") -> None:
    """Write the captured home store and its service records, refreshing their time in place.

    Only the straight cut is established by a store page showing a cut desk. The
    special cuts have national prices but their availability per market is not
    published, so they are recorded as unknown, never as absent.
    """
    captured_at = datetime.now(UTC)
    values = {
        "store_key": capture.store_key, "source_site": source_site, "name": capture.name,
        "address": capture.address, "phone": capture.phone, "market_id": capture.market_id,
        "url": capture.url, "captured_at": captured_at,
    }
    session.execute(
        insert(Store).values(**values).on_conflict_do_update(
            index_elements=[Store.store_key], set_={k: v for k, v in values.items() if k != "store_key"}
        )
    )
    for service, price_cents in NATIONAL_CUT_PRICES.items():
        if service == "gerader_zuschnitt":
            availability = ServiceAvailability.PERFORMED if capture.offers_cutting else ServiceAvailability.UNKNOWN
        else:
            availability = ServiceAvailability.UNKNOWN
        session.execute(
            insert(StoreService).values(
                store_key=capture.store_key, service=service, availability=availability.value,
                price_cents=price_cents, url=CUT_SERVICE_URL, captured_at=captured_at,
            ).on_conflict_do_update(
                constraint="uq_store_service",
                set_={
                    "availability": availability.value, "price_cents": price_cents,
                    "url": CUT_SERVICE_URL, "captured_at": captured_at,
                },
            )
        )


def ingest_home_store(
    session: Session, fetcher: PacedFetcher, store_key: str, *, base_url: str = TOOM_BASE
) -> StoreRunReport:
    """Capture the one home store from its own page, after reading the site's rules.

    A site that refuses its rules or the page is reported, never retried under
    another identity; the owner's recorded restrictions are never touched.
    """
    report = StoreRunReport()
    url = f"{base_url}/m/{store_key}/"
    try:
        rules = fetcher.fetch_rules(base_url, source="toom")
    except RulesUnavailable as refusal:
        report.failures.append(f"{url}: {refusal.reason}")
        return report
    if not rules.allows(url):
        report.failures.append(f"{url}: excluded by {base_url}{RULES_PATH}")
        return report
    try:
        page = fetcher.fetch_auxiliary(url)
        page.raise_for_status()
        capture = parse_store_page(url, page.text)
        capture.store_key = store_key
        upsert_store(session, capture)
        session.commit()
        report.stores = 1
        report.services = len(NATIONAL_CUT_PRICES)
    except Exception as error:  # noqa: BLE001 - one page must not crash the command
        session.rollback()
        report.failures.append(f"{url} ({type(error).__name__})")
        logger.warning("store page %s failed: %s", url, error)
    return report


def delete_restriction(session: Session, store_key: str, restriction: RestrictionKind) -> bool:
    """Remove one owner-recorded limit; `False` when there was none."""
    require_store(session, store_key)
    row = session.scalar(
        select(StoreCutRestriction).where(
            StoreCutRestriction.store_key == store_key,
            StoreCutRestriction.restriction == restriction.value,
        )
    )
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True
