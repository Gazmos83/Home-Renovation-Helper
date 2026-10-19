"""price_cut_list: materials, sheet yield, cut classification (cut-list-pricing spec).

`material_key` is the one place a cutlist/hardware material string becomes a
price-list key (design.md decision 2). It never guesses: a phrase the fixed
vocabulary does not recognise yields `unknown:<slug>` rather than the nearest
match, because a probabilistic guess has no place under a client-facing
figure (design.md decision 2's rejected alternative).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.blender import storage
from app.blender.custom_build.derive import derive, drilling, supply_note
from app.config import Settings
from app.db.models import (
    CutListPricing,
    CutListPricingEntry,
    PieceVersion,
    SupplierPrice,
    SupplierPriceUnit,
)
from app.pricing import price_list
from app.pricing import remnants as remnant_rack
from app.pricing.errors import NotApproved, NotFound, Refused
from app.pricing.price_list import PERSONAL_SUPPLY_KEY
from app.pricing.store import (
    SERVICE_FOR_GEOMETRY,
    CutGeometry,
    CutOutcome,
    CutSpec,
    classify_cut,
    find_service,
    require_store,
)

# Longest/most specific phrase first: "oak-veneered birch" must be matched
# before the bare "birch" fallback, or every oak-veneered part would be
# mis-classified as plain birch. Each of these is a panel family — a sheet
# material priced per its thickness — so a match without a parseable leading
# thickness is not returned as a class on its own; it falls through to
# `unknown` instead of guessing one.
#
# The families after the first four are the sheets toom sells and the catalog
# holds (material-review-on-import), each by its German name and its English
# equivalent. "multiplex birch" must precede the bare "birch", and "black mdf"
# the bare "mdf". The class names are passed unchanged to the store
# directory's cut classification, which has no material mapping of its own.
_PANEL_CLASS_PHRASES: Final[list[tuple[str, str]]] = [
    ("oak-veneered birch", "oak-veneer-birch"),
    ("multiplexplatte birke", "multiplex-birch"),
    ("multiplex birke", "multiplex-birch"),
    ("multiplex birch", "multiplex-birch"),
    ("birch multiplex", "multiplex-birch"),
    ("birch plywood", "birch-ply"),
    ("leimholzplatte fichte", "leimholz-spruce"),
    ("leimholz fichte", "leimholz-spruce"),
    ("leimholz spruce", "leimholz-spruce"),
    ("spruce leimholz", "leimholz-spruce"),
    ("leimholzplatte buche", "leimholz-beech"),
    ("leimholz buche", "leimholz-beech"),
    ("leimholz beech", "leimholz-beech"),
    ("beech leimholz", "leimholz-beech"),
    ("tischlerplatte", "tischlerplatte"),
    ("blockboard", "tischlerplatte"),
    ("möbelbauplatte", "moebelbauplatte"),
    ("moebelbauplatte", "moebelbauplatte"),
    ("furniture board", "moebelbauplatte"),
    ("birch", "birch"),
    ("black mdf", "black-mdf"),
    ("mdf", "mdf"),
]

# "18 mm oak-veneered birch" -> thickness "18". Anchored to the start: a
# cross-section spec like "25×25×2 mm SHS" has no *leading* "<n> mm" (the
# digits before "mm" are "×25×2", not a bare integer), so this deliberately
# does not extract a thickness for it.
_LEADING_THICKNESS = re.compile(r"^(\d+)\s*mm\b")
# The steel rail's cross-section size ("25×25×2 mm SHS" -> "25"): the first
# digit run anywhere in the text, since it is never in leading-thickness form.
_FIRST_INT = re.compile(r"\d+")

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_INVALID.sub("-", text.strip().casefold()).strip("-")
    return slug or "material"


def material_key(text: str) -> str:
    """A cutlist/hardware material string to a stable price-list key.

    `panel:<class>:<thickness_mm>` for a sheet material whose leading
    thickness parses; `stock:<class>` for non-panel stock (steel, aluminium),
    where a thickness is not the relevant figure; `unknown:<slug>` for
    anything the vocabulary does not recognise.
    """
    lowered = text.strip().casefold()
    thickness_match = _LEADING_THICKNESS.match(lowered)
    thickness = thickness_match.group(1) if thickness_match else None

    for phrase, class_name in _PANEL_CLASS_PHRASES:
        if phrase in lowered:
            if thickness is not None:
                return f"panel:{class_name}:{thickness}"
            break

    if "shs" in lowered:
        size_match = _FIRST_INT.search(lowered)
        if size_match is not None:
            return f"stock:steel-shs-{size_match.group()}"

    if "aluminium" in lowered and "flat bar" in lowered:
        return "stock:aluminium-flat"

    return f"unknown:{_slugify(text)}"


# --- sheet yield (design.md decision 3) -----------------------------------------------
#
# First-fit-decreasing shelf packing, grain-locked. A shelf runs along the
# sheet's length axis; shelves stack along its width axis. Parts are sorted
# by width (their shelf-height footprint) then length, both descending, so
# the tallest, widest parts open new shelves first and everything after them
# can only ever be shorter — the classic FFDH invariant that lets a later,
# smaller part reuse any earlier shelf without re-checking every part on it.
# A new shelf may open on any sheet that still has free height, earliest
# first, so a short part can use a gap left on an earlier sheet. Remnant
# sheets, when supplied, are filled before a purchase sheet is opened.
# Not an optimal packer by design (design.md's rejected alternative): the
# figure is an estimate to carry to the store, shown with its utilisation.
#
# The shared-cut count is one rip per shelf plus one crosscut per piece on
# that shelf. The crosscut that frees a piece is the first edge of the next,
# so it is counted once: two pieces on one shelf are 3 cuts, not two cuts
# for each piece. A lone piece is still one rip and one crosscut, because
# the shelf is the sheet length and the piece is cut off the leftover.

DEFAULT_KERF_MM: Final = 4


@dataclass(frozen=True, slots=True)
class Part:
    """One cutlist part type, as `price_cut_list` reads it from `cutlist.csv`.

    `pack_sheets` expands `qty` into individual instances itself; `id` is
    carried onto each instance's `Placement` so results stay traceable back
    to the row that produced them.
    """

    id: str
    length_mm: int
    width_mm: int
    qty: int = 1
    grain_locked: bool = False


@dataclass(frozen=True, slots=True)
class RemnantStock:
    """One rack row the packer may fill before it buys a sheet.

    `quantity` is how many identical sheets that row holds. Packing names
    the sheets it planned to use and does not change the rack.
    """

    id: str
    length_mm: int
    width_mm: int
    grain_axis: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class Placement:
    """Where one instance of a part landed. `rotated` is always `False` for
    a grain-locked part - it is never given the option.

    `sheet_index` counts purchase sheets, or copies of one remnant, from 0.
    `shelf_index` counts shelves on that sheet from 0. `remnant_id` is set
    when the part sits on a remnant rather than a sheet to buy.
    """

    part_id: str
    sheet_index: int
    shelf_index: int
    length_mm: int
    width_mm: int
    rotated: bool
    remnant_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemnantUse:
    """How many copies of one remnant row this plan used."""

    remnant_id: str
    sheets: int


@dataclass(frozen=True, slots=True)
class PackResult:
    sheet_count: int
    utilisation_percent: float
    placements: tuple[Placement, ...]
    unfitting: tuple[Part, ...]
    shared_cut_count: int
    remnants_used: tuple[RemnantUse, ...]


class _Sheet:
    """One physical sheet, remnant or purchase. Never exposed."""

    __slots__ = (
        "grain_axis",
        "length",
        "remnant_id",
        "sheet_index",
        "shelf_count",
        "used_height",
        "width",
    )

    def __init__(
        self,
        sheet_index: int,
        length: int,
        width: int,
        remnant_id: str | None,
        grain_axis: str,
    ) -> None:
        self.sheet_index = sheet_index
        self.length = length
        self.width = width
        self.remnant_id = remnant_id
        self.grain_axis = grain_axis
        self.used_height = 0
        self.shelf_count = 0


class _Shelf:
    """Mutable packing state for one shelf. Never exposed outside this module."""

    __slots__ = ("height", "remaining_length", "sheet", "shelf_index")

    def __init__(self, sheet: _Sheet, shelf_index: int, height: int, remaining_length: int) -> None:
        self.sheet = sheet
        self.shelf_index = shelf_index
        self.height = height
        self.remaining_length = remaining_length


def _grain_allows(grain_locked: bool, grain_axis: str) -> bool:
    """A length-locked part only sits on a sheet whose grain runs along the length."""
    return grain_axis == "length" if grain_locked else True


def _shared_cut_count(placements: Sequence[Placement]) -> int:
    """One rip per shelf, plus one crosscut per piece on that shelf."""
    pieces: dict[tuple[str | None, int, int], int] = {}
    for placement in placements:
        key = (placement.remnant_id, placement.sheet_index, placement.shelf_index)
        pieces[key] = pieces.get(key, 0) + 1
    return sum(1 + count for count in pieces.values())


def _remnants_used(placements: Sequence[Placement]) -> tuple[RemnantUse, ...]:
    copies: dict[str, set[int]] = {}
    for placement in placements:
        if placement.remnant_id is None:
            continue
        copies.setdefault(placement.remnant_id, set()).add(placement.sheet_index)
    return tuple(
        RemnantUse(remnant_id, len(indexes))
        for remnant_id, indexes in sorted(copies.items())
    )


def pack_sheets(
    parts: list[Part],
    sheet_length_mm: int,
    sheet_width_mm: int,
    kerf_mm: int = DEFAULT_KERF_MM,
    remnants: Sequence[RemnantStock] | None = None,
) -> PackResult:
    """Pack every part (expanded by its `qty`) onto remnants, then purchase sheets.

    A grain-locked part always keeps its `length_mm` along the sheet's length
    axis, and only on a remnant whose grain axis is `length`; an unlocked
    part may rotate and may use any remnant of the material. A part that fits
    neither orientation of a remnant nor of a single empty purchase sheet is
    returned separately as unfitting rather than forced (cut-list-pricing
    "An oversize part cannot be forced"). Deterministic for the same input
    regardless of `parts`' original order, because the sort key never depends
    on it except as a final, stable tie-breaker on `id`.
    """
    instances: list[tuple[str, int, int, bool]] = []
    for part in parts:
        for _ in range(part.qty):
            instances.append((part.id, part.length_mm, part.width_mm, part.grain_locked))
    instances.sort(key=lambda item: (-item[2], -item[1], item[0]))

    sheets: list[_Sheet] = []
    next_copy: dict[str, int] = {}
    for remnant in remnants or ():
        for _ in range(remnant.quantity):
            index = next_copy.get(remnant.id, 0)
            next_copy[remnant.id] = index + 1
            sheets.append(
                _Sheet(index, remnant.length_mm, remnant.width_mm, remnant.id, remnant.grain_axis)
            )
    purchase_count = 0

    shelves: list[_Shelf] = []
    placements: list[Placement] = []
    unfitting: list[Part] = []

    def orientations(length: int, width: int, grain_locked: bool) -> list[tuple[int, int, bool]]:
        options = [(length, width, False)]
        if not grain_locked:
            options.append((width, length, True))
        return options

    def place_on_new_shelf(
        sheet: _Sheet, part_id: str, length_mm: int, width_mm: int, rotated: bool
    ) -> None:
        shelf_index = sheet.shelf_count
        sheet.shelf_count += 1
        sheet.used_height += width_mm + kerf_mm
        # A kerf is charged after every piece, but the sheet's own edge needs no cut,
        # so the free length is `sheet.length + kerf - (length + kerf)`.
        shelves.append(
            _Shelf(sheet, shelf_index, width_mm + kerf_mm, sheet.length - length_mm)
        )
        placements.append(
            Placement(
                part_id,
                sheet.sheet_index,
                shelf_index,
                length_mm,
                width_mm,
                rotated,
                sheet.remnant_id,
            )
        )

    for part_id, length, width, grain_locked in instances:
        options = orientations(length, width, grain_locked)
        placed = False

        for shelf in shelves:
            if not _grain_allows(grain_locked, shelf.sheet.grain_axis):
                continue
            for along, across, rotated in options:
                if (
                    across + kerf_mm <= shelf.height
                    and along + kerf_mm <= shelf.remaining_length
                ):
                    shelf.remaining_length -= along + kerf_mm
                    placements.append(
                        Placement(
                            part_id,
                            shelf.sheet.sheet_index,
                            shelf.shelf_index,
                            along,
                            across,
                            rotated,
                            shelf.sheet.remnant_id,
                        )
                    )
                    placed = True
                    break
            if placed:
                break

        if not placed:
            for sheet in sheets:
                if not _grain_allows(grain_locked, sheet.grain_axis):
                    continue
                for along, across, rotated in options:
                    # No kerf against the sheet's edge (see `place_on_new_shelf`).
                    if along <= sheet.length and sheet.used_height + across <= sheet.width:
                        place_on_new_shelf(sheet, part_id, along, across, rotated)
                        placed = True
                        break
                if placed:
                    break

        if placed:
            continue

        fitting = [
            (along, across, rotated)
            for along, across, rotated in options
            if along <= sheet_length_mm and across <= sheet_width_mm
        ]
        if not fitting:
            unfitting.append(Part(part_id, length, width, 1, grain_locked))
            continue
        along, across, rotated = fitting[0]
        sheet = _Sheet(purchase_count, sheet_length_mm, sheet_width_mm, None, "length")
        purchase_count += 1
        sheets.append(sheet)
        place_on_new_shelf(sheet, part_id, along, across, rotated)

    purchase_area = sum(
        placement.length_mm * placement.width_mm
        for placement in placements
        if placement.remnant_id is None
    )
    sheet_area_mm2 = sheet_length_mm * sheet_width_mm
    utilisation_percent = (
        (purchase_area / (sheet_area_mm2 * purchase_count)) * 100
        if purchase_count and sheet_area_mm2
        else 0.0
    )

    return PackResult(
        sheet_count=purchase_count,
        utilisation_percent=utilisation_percent,
        placements=tuple(placements),
        unfitting=tuple(unfitting),
        shared_cut_count=_shared_cut_count(placements),
        remnants_used=_remnants_used(placements),
    )


def sheet_cost(entry: SupplierPrice, sheets: int) -> int | None:
    """The materials cost of `sheets` whole panels of `entry`, in cents.

    `None` when the entry has no effective price - unpriced, never a
    fabricated figure. A `per_m2` entry is charged for the whole sheet area
    (the retailer sells whole panels, design.md decision 3); a `per_piece`
    entry is charged per sheet. Rounded half-up to the cent.
    """
    if sheets == 0:
        return 0
    price = entry.effective_cents
    if price is None:
        return None

    if entry.unit == SupplierPriceUnit.PER_PIECE:
        return price * sheets

    if entry.unit == SupplierPriceUnit.PER_M2:
        if entry.sheet_length_mm is None or entry.sheet_width_mm is None:
            return None
        area_m2 = Decimal(entry.sheet_length_mm) * Decimal(entry.sheet_width_mm) / Decimal(1_000_000)
        total = Decimal(price) * area_m2 * sheets
        return int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    # per_metre/per_cut entries are not sheet-priced.
    return None


# --- price_cut_list (design.md decisions 4-5) -------------------------------------------

_REVIEW_KEYWORDS: Final = ("grommet", "hole", "cut-out", "cutout", "mitre", "miter", "ø")
_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)")

# What the workshop supplies itself (supplier-price-list's reserved entry): a
# cut-list row whose notes carry the derivation's supply mark, and a hardware
# row whose id starts with the prefix, both resolve to `Personal_Supply`.
PERSONAL_SUPPLY_MARK: Final = supply_note(PERSONAL_SUPPLY_KEY)
PERSONAL_SUPPLY_HARDWARE_PREFIX: Final = f"{PERSONAL_SUPPLY_KEY}-"


def _review_note(notes: str) -> str | None:
    lowered = notes.casefold()
    return notes if any(keyword in lowered for keyword in _REVIEW_KEYWORDS) else None


def _leading_number(text: str) -> Decimal | None:
    match = _LEADING_NUMBER.match(text)
    return Decimal(match.group(1)) if match else None


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _entry_snapshot(entry: SupplierPrice) -> dict[str, Any]:
    """The price an entry was used at, and where it came from: the override, or its provenance."""
    return {
        "key": entry.key,
        "cents": entry.effective_cents,
        "origin": "override" if entry.override_cents is not None else entry.provenance,
        "unconfirmed": entry.unconfirmed,
    }


def _grain_locked(grain: str) -> bool:
    return grain.strip().casefold().startswith("length")


_CHARGE_MODES: Final = frozenset({"shared", "per_cut"})
_NO_BAND: Final = frozenset({"", "none", "-", "–", "—"})
_ALL_EDGES: Final = frozenset({"all edges", "all four edges"})
_BAND_SLUG = re.compile(r"[^a-z0-9]+")


def _known_charge_mode(mode: str | None) -> str | None:
    if mode is None or not str(mode).strip():
        return None
    chosen = str(mode).strip()
    if chosen not in _CHARGE_MODES:
        raise Refused(f"unknown cut-charge mode: {chosen!r}; choose shared or per_cut")
    return chosen


@dataclass(frozen=True, slots=True)
class BandNeed:
    """One band's summed length, before it is rounded up to bundles."""

    key: str
    label: str
    length_mm: int


def _band_slug(label: str) -> str:
    slug = _BAND_SLUG.sub("-", label.casefold()).strip("-")
    return slug or "edge"


def banding_requirement(rows: Sequence[dict[str, str]]) -> tuple[BandNeed, ...]:
    """Turn cut-row banding labels into lengths. Hardware rows are not read.

    `none`, a blank, and a dash add nothing. A `leimholz` material adds
    nothing even when a label is present. `front edge` and `top edge`, and
    any other single-edge label, contribute the part's length once.
    `all edges` and `all four edges` contribute the perimeter. Quantity
    multiplies. Lengths of the same band are summed.
    """
    totals: dict[str, list[str | int]] = {}
    for row in rows:
        if "leimholz" in material_key(row.get("material", "")):
            continue
        label = (row.get("banding") or "").strip()
        folded = label.casefold()
        if folded in _NO_BAND or folded.startswith("none"):
            continue
        qty = int(row.get("qty") or 0)
        length_mm = int(row.get("l") or 0)
        width_mm = int(row.get("w") or 0)
        if folded in _ALL_EDGES:
            key = "band:all-edges"
            display = "all edges"
            length = 2 * (length_mm + width_mm) * qty
        else:
            key = f"band:{_band_slug(folded)}"
            display = label
            length = length_mm * qty
        bucket = totals.setdefault(key, [display, 0])
        bucket[1] = int(bucket[1]) + length
    return tuple(
        BandNeed(key, str(totals[key][0]), int(totals[key][1])) for key in sorted(totals)
    )


def _bundle_count(length_mm: int, bundle_length_mm: int) -> int:
    return (length_mm + bundle_length_mm - 1) // bundle_length_mm


def _placement_json(placement: Placement) -> dict[str, Any]:
    return {
        "part_id": placement.part_id,
        "sheet_index": placement.sheet_index,
        "shelf_index": placement.shelf_index,
        "length_mm": placement.length_mm,
        "width_mm": placement.width_mm,
        "rotated": placement.rotated,
        "remnant_id": placement.remnant_id,
    }


def _charge_bands(
    rows: list[dict[str, str]],
    entries_by_key: dict[str, SupplierPrice],
    entries_used: dict[UUID, SupplierPrice],
    unpriced: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Price each band as whole bundles. A missing entry or bundle length is unpriced."""
    materials_added = 0
    unpriced_added = 0
    lines: list[dict[str, Any]] = []
    for need in banding_requirement(rows):
        entry = entries_by_key.get(need.key)
        bundle_length = entry.bundle_length_mm if entry is not None else None
        bundles = _bundle_count(need.length_mm, bundle_length) if bundle_length else None
        cost: int | None = None
        reason: str | None = None
        if entry is None:
            reason = "no price-list entry for this band"
        elif bundle_length is None:
            reason = "the band entry has no bundle length"
        elif entry.effective_cents is None:
            reason = "the band entry has no effective price"
        elif bundles is None:
            reason = "the band entry has no bundle length"
        elif entry.unit == SupplierPriceUnit.PER_PIECE:
            cost = entry.effective_cents * bundles
        elif entry.unit == SupplierPriceUnit.PER_METRE:
            metres = Decimal(bundles * bundle_length) / Decimal(1000)
            cost = _round_half_up(metres * Decimal(entry.effective_cents))
        else:
            reason = "the band entry's unit cannot price a bundle"
        line: dict[str, Any] = {
            "key": need.key,
            "label": need.label,
            "length_mm": need.length_mm,
            "bundle_length_mm": bundle_length,
            "bundles": bundles,
            "cost_cents": cost,
        }
        if cost is None:
            unpriced_added += 1
            unpriced.append({"kind": "banding", **line, "reason": reason})
        else:
            materials_added += cost
            entries_used[entry.id] = entry
        lines.append(line)
    return lines, materials_added, unpriced_added


def version_approved(session: Session, package_id: str, version: int) -> bool:
    """Whether the owner has approved this version (a version with no record is not approved)."""
    row = session.get(PieceVersion, (package_id, version))
    return row is not None and row.approved_at is not None


def price_cut_list(
    session: Session,
    root: Path,
    package_id: str,
    version: int,
    settings: Settings,
    *,
    store_key: str | None = None,
    delivery_key: str | None = None,
    cut_charge_mode: str | None = None,
) -> CutListPricing:
    """Price one package version's cut list against the home store's cut services.

    Parts are packed onto sheets (remnants first), cuts are classified against the
    store and the owner's recorded limits, bands are bought in whole bundles, and
    every line without a price is listed by name and marks the pricing incomplete:
    nothing is guessed. Only an approved version is priced; an unapproved one is refused
    before anything is packed or written. Each call writes a new immutable record; nothing here calls a
    language model, starts Blender or changes the rack. Flushes; the caller commits.
    """
    charge_mode = _known_charge_mode(cut_charge_mode)
    folder = storage.version_dir(root, package_id, version)
    try:
        document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused(f"{package_id} version {version} has no readable document to price") from None
    if not version_approved(session, package_id, version):
        raise NotApproved(
            f"{package_id} version {version} is not approved; approve it first on the Pieces "
            "page or in the conversation's project panel, then ask for the price again"
        )
    # The rows are what the version derives from its own document: the same rows
    # `cut_list` shows and the cut list a build writes, so an unbuilt version is priced too.
    hardware_inputs = storage.read_hardware_inputs(folder)
    parts, hardware, _assembly = derive(document, hardware_inputs)
    cutlist_rows = [{key: str(value) for key, value in row.items()} for row in parts]
    hardware_rows = [{key: str(value) for key, value in row.items()} for row in hardware]
    if not cutlist_rows:
        raise Refused("this version has no cut list yet")

    resolved_store_key = store_key or settings.toom_home_store
    require_store(session, resolved_store_key)

    entries_by_key: dict[str, SupplierPrice] = {
        entry.key: entry for entry in price_list.list_entries(session)
    }

    delivery_entry: SupplierPrice | None = None
    if delivery_key is not None:
        delivery_entry = entries_by_key.get(delivery_key)
        if delivery_entry is None or delivery_entry.category != "delivery":
            raise Refused(f"no delivery option with key {delivery_key!r}")

    entries_used: dict[UUID, SupplierPrice] = {}
    materials_cents = 0
    hardware_cents = 0
    banding_cents = 0
    cut_service_cents = 0
    custom_count = 0
    undetermined_count = 0
    review_count = 0
    unpriced_count = 0
    total_unfitting = 0

    materials_result: dict[str, Any] = {}
    workshop: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    undetermined: list[dict[str, Any]] = []
    unpriced: list[dict[str, Any]] = []
    unfitting_result: list[dict[str, Any]] = []
    hardware_result: list[dict[str, Any]] = []

    personal_entry = entries_by_key.get(PERSONAL_SUPPLY_KEY)
    personal_supply: list[dict[str, Any]] = []

    def supply_line(kind: str, identifier: str, name: str, qty_text: str) -> None:
        """One part or hardware line the workshop supplies itself, at the reserved entry's price."""
        nonlocal materials_cents, hardware_cents, unpriced_count
        quantity = _leading_number(qty_text)
        cost: int | None = None
        if personal_entry is not None and personal_entry.effective_cents is not None and quantity is not None:
            cost = _round_half_up(quantity * Decimal(personal_entry.effective_cents))
        line = {"kind": kind, "id": identifier, "name": name, "qty": qty_text, "cost_cents": cost}
        if cost is None:
            unpriced_count += 1
            unpriced.append(
                {**line, "material_key": PERSONAL_SUPPLY_KEY,
                 "reason": f"the {PERSONAL_SUPPLY_KEY} entry is missing or has no effective price"}
            )
        else:
            if kind == "hardware":
                hardware_cents += cost
            else:
                materials_cents += cost
            entries_used[personal_entry.id] = personal_entry  # type: ignore[union-attr]
        personal_supply.append(line)

    rows_by_key: dict[str, list[dict[str, str]]] = {}
    for row in cutlist_rows:
        if PERSONAL_SUPPLY_MARK in row["notes"]:
            supply_line("part", row["id"], row["name"], row["qty"])
            continue
        rows_by_key.setdefault(material_key(row["material"]), []).append(row)

    for key in sorted(rows_by_key):
        rows = rows_by_key[key]

        if key.startswith("panel:"):
            entry = entries_by_key.get(key)
            cuts: list[dict[str, Any]] = []

            for row in rows:
                length_mm, width_mm, thickness_mm = int(row["l"]), int(row["w"]), int(row["t"])
                qty = int(row["qty"])
                class_name = key.split(":")[1]
                note_flag = _review_note(row["notes"])
                if note_flag is not None:
                    review_count += 1
                    review.append(
                        {"part_id": row["id"], "name": row["name"], "note": note_flag}
                    )
                    cuts.append(
                        {
                            "part_id": row["id"],
                            "name": row["name"],
                            "qty": qty,
                            "status": "review",
                        }
                    )
                    continue

                classification = classify_cut(
                    session,
                    resolved_store_key,
                    CutSpec(
                        geometry=CutGeometry.STRAIGHT,
                        length_mm=length_mm,
                        width_mm=width_mm,
                        thickness_mm=thickness_mm,
                        material=class_name,
                    ),
                )
                cut_line = {
                    "part_id": row["id"],
                    "name": row["name"],
                    "qty": qty,
                    "status": classification.outcome.value,
                    "reason": classification.reason,
                }
                if classification.outcome is CutOutcome.COVERED:
                    # The unit price stays on the line. The cut-service total
                    # is the shared-cut count times the store tariff, and only
                    # when the operator chose per_cut — never two cuts per piece.
                    cut_line["cut_price_cents"] = classification.price_cents
                elif classification.outcome is CutOutcome.CUSTOM:
                    custom_count += 1
                    cut_line["restriction"] = classification.restriction
                    cut_line["restriction_value"] = classification.restriction_value
                    workshop.append(
                        {
                            "part_id": row["id"],
                            "name": row["name"],
                            "qty": qty,
                            "material_key": key,
                            "reason": classification.reason,
                        }
                    )
                else:  # UNDETERMINED
                    undetermined_count += 1
                    undetermined.append(
                        {"part_id": row["id"], "name": row["name"], "reason": classification.reason}
                    )
                cuts.append(cut_line)

            material_entry: dict[str, Any] = {"cuts": cuts}
            if entry is None:
                unpriced_count += 1
                material_entry["cost_cents"] = None
                for row in rows:
                    unpriced.append(
                        {
                            "kind": "material",
                            "part_id": row["id"],
                            "name": row["name"],
                            "material_key": key,
                            "reason": "no price-list entry for this material",
                        }
                    )
            else:
                parts = [
                    Part(
                        id=row["id"],
                        length_mm=int(row["l"]),
                        width_mm=int(row["w"]),
                        qty=int(row["qty"]),
                        grain_locked=_grain_locked(row["grain"]),
                    )
                    for row in rows
                ]
                stock = [
                    RemnantStock(
                        id=str(remnant.id),
                        length_mm=remnant.length_mm,
                        width_mm=remnant.width_mm,
                        grain_axis=remnant.grain_axis,
                        quantity=remnant.quantity,
                    )
                    for remnant in remnant_rack.matching_stock(session, key)
                ]
                pack_result = pack_sheets(
                    parts,
                    entry.sheet_length_mm or 0,
                    entry.sheet_width_mm or 0,
                    remnants=stock,
                )
                for unfit in pack_result.unfitting:
                    total_unfitting += 1
                    unfitting_result.append(
                        {
                            "part_id": unfit.id,
                            "material_key": key,
                            "length_mm": unfit.length_mm,
                            "width_mm": unfit.width_mm,
                        }
                    )
                cost = sheet_cost(entry, pack_result.sheet_count)
                material_entry.update(
                    {
                        "product": _entry_snapshot(entry),
                        "sheet_count": pack_result.sheet_count,
                        "utilisation_percent": pack_result.utilisation_percent,
                        "cost_cents": cost,
                        "placements": [_placement_json(item) for item in pack_result.placements],
                        "shared_cut_count": pack_result.shared_cut_count,
                        "remnants_used": [
                            {"remnant_id": use.remnant_id, "sheets": use.sheets}
                            for use in pack_result.remnants_used
                        ],
                    }
                )
                if cost is None:
                    unpriced_count += 1
                    unpriced.append(
                        {
                            "kind": "material",
                            "material_key": key,
                            "reason": "the price-list entry has no effective price",
                        }
                    )
                else:
                    materials_cents += cost
                    entries_used[entry.id] = entry
            materials_result[key] = material_entry

        elif key.startswith("stock:") or (key.startswith("unknown:") and key in entries_by_key):
            # An unrecognised phrase the operator has named in the price list
            # is workshop stock too: priced by its entry, never cut-classified.
            entry = entries_by_key.get(key)
            named = key.startswith("unknown:")
            for row in rows:
                qty = int(row["qty"])
                length_mm = int(row["l"])
                cost: int | None = None
                if entry is not None and entry.effective_cents is not None:
                    if entry.unit == SupplierPriceUnit.PER_PIECE:
                        cost = entry.effective_cents * qty
                    elif entry.unit == SupplierPriceUnit.PER_METRE:
                        cost = _round_half_up(
                            Decimal(qty) * (Decimal(length_mm) / Decimal(1000)) * Decimal(entry.effective_cents)
                        )
                    elif named and entry.unit == SupplierPriceUnit.PER_M2:
                        area_m2 = Decimal(length_mm) * Decimal(int(row["w"])) / Decimal(1_000_000)
                        cost = _round_half_up(Decimal(qty) * area_m2 * Decimal(entry.effective_cents))
                line: dict[str, Any] = {
                    "part_id": row["id"],
                    "name": row["name"],
                    "qty": qty,
                    "material_key": key,
                    "cost_cents": cost,
                }
                if cost is None:
                    unpriced_count += 1
                    line["reason"] = (
                        "no price-list entry for this material"
                        if entry is None
                        else "the price-list entry has no effective price or a mismatched unit"
                    )
                    unpriced.append({"kind": "material", **line})
                else:
                    materials_cents += cost
                    entries_used[entry.id] = entry
                workshop.append(line)

        else:  # unknown:*
            unpriced_count += 1
            for row in rows:
                unpriced.append(
                    {
                        "kind": "material",
                        "part_id": row["id"],
                        "name": row["name"],
                        "material_key": key,
                        "reason": (
                            "this material phrase is not recognised; create a price-list entry "
                            f"with key {key!r} to price it"
                        ),
                    }
                )

    for row in hardware_rows:
        if row["id"].startswith(PERSONAL_SUPPLY_HARDWARE_PREFIX):
            supply_line("hardware", row["id"], row["item"], row["qty"])
            continue
        entry = entries_by_key.get(row["id"])
        quantity = _leading_number(row["qty"])
        cost = None
        if entry is not None and entry.effective_cents is not None and quantity is not None:
            cost = _round_half_up(quantity * Decimal(entry.effective_cents))
        line = {
            "id": row["id"],
            "item": row["item"],
            "qty": row["qty"],
            "cost_cents": cost,
        }
        if cost is None:
            unpriced_count += 1
            line["reason"] = (
                f"no quantity ({row['notes']})"
                if not row["qty"].strip()
                else "no price-list entry for this hardware item"
                if entry is None
                else "the quantity or the price-list entry's price could not be resolved"
            )
            unpriced.append({"kind": "hardware", **line})
        else:
            hardware_cents += cost
            entries_used[entry.id] = entry
        hardware_result.append(line)

    delivery_line: dict[str, Any] | None = None
    delivery_cents = 0
    if delivery_entry is not None:
        delivery_line = {"key": delivery_entry.key, "cents": delivery_entry.effective_cents}
        entries_used[delivery_entry.id] = delivery_entry
        if delivery_entry.effective_cents is None:
            unpriced_count += 1
            unpriced.append({"kind": "delivery", "key": delivery_entry.key,
                             "reason": "the delivery entry has no effective price"})
        else:
            delivery_cents = delivery_entry.effective_cents

    band_lines, band_cents, band_unpriced = _charge_bands(
        cutlist_rows, entries_by_key, entries_used, unpriced
    )
    banding_cents += band_cents
    unpriced_count += band_unpriced

    shared_cut_count = sum(
        int(item.get("shared_cut_count") or 0) for item in materials_result.values()
    )
    remnants_used: list[dict[str, Any]] = []
    for item in materials_result.values():
        remnants_used.extend(item.get("remnants_used") or [])

    straight = find_service(
        session, resolved_store_key, SERVICE_FOR_GEOMETRY[CutGeometry.STRAIGHT]
    )
    straight_price = straight.price_cents if straight is not None and straight.price_is_known else None
    per_cut_fee = None if straight_price is None else shared_cut_count * straight_price
    if charge_mode == "per_cut":
        if straight_price is None:
            unpriced_count += 1
            unpriced.append(
                {
                    "kind": "cut_service",
                    "reason": "the store has no recorded straight-cut price",
                }
            )
            cut_service_cents = 0
        else:
            cut_service_cents = per_cut_fee
    else:
        cut_service_cents = 0

    drilling_result: dict[str, Any] | None = None
    if hardware_inputs is not None:
        counts = drilling(document, hardware_inputs)["counts"]
        borings = counts["hinge_cup_borings"]
        boring_service = find_service(
            session, resolved_store_key, SERVICE_FOR_GEOMETRY[CutGeometry.HINGE_BORING]
        )
        boring_price = (
            boring_service.price_cents if boring_service is not None and boring_service.price_is_known else None
        )
        boring_fee = None if boring_price is None else borings * boring_price
        if charge_mode == "per_cut" and borings:
            if boring_fee is None:
                unpriced_count += 1
                unpriced.append(
                    {
                        "kind": "cut_service",
                        "reason": "the store has no recorded hinge-boring (topfband_bohrung) price",
                    }
                )
            else:
                cut_service_cents += boring_fee
        drilling_result = {
            "hinge_cup_borings": borings,
            "hinge_boring_fee_cents": boring_fee if charge_mode == "per_cut" else None,
            # Holes are listed, not priced; None when they are blank or given as a rule in words.
            "shelf_pin_holes": counts.get("shelf_pin_holes"),
        }

    complete = unpriced_count == 0 and undetermined_count == 0 and total_unfitting == 0

    result: dict[str, Any] = {
        "materials": materials_result,
        "workshop": workshop,
        "review": review,
        "undetermined": undetermined,
        "hardware": hardware_result,
        "unpriced": unpriced,
        "personal_supply": personal_supply,
        "unfitting": unfitting_result,
        "entries_used": [_entry_snapshot(entry) for entry in entries_used.values()],
        "delivery": delivery_line,
        "sources": {"cutlist": "derived from the version's document", "hardware": "derived from the version's document"},
        "shared_cut_count": shared_cut_count,
        "cut_charge_mode": charge_mode,
        "cut_charge_choice_open": charge_mode is None,
        "per_cut_fee_cents": per_cut_fee,
        "remnants_used": remnants_used,
        "banding": band_lines,
    }
    if drilling_result is not None:
        result["drilling"] = drilling_result

    total_cents = (
        materials_cents + hardware_cents + banding_cents + cut_service_cents + delivery_cents
    )
    row_id = uuid4()
    pricing_row = CutListPricing(
        id=row_id,
        package_id=package_id,
        version=version,
        store_key=resolved_store_key,
        computed_at=datetime.now(UTC),
        materials_cents=materials_cents,
        cut_service_cents=cut_service_cents,
        banding_cents=banding_cents,
        hardware_cents=hardware_cents,
        delivery_cents=delivery_cents,
        total_cents=total_cents,
        complete=complete,
        custom_count=custom_count,
        undetermined_count=undetermined_count,
        review_count=review_count,
        unpriced_count=unpriced_count,
        result=result,
        cut_charge_mode=charge_mode,
    )
    session.add(pricing_row)
    for entry in entries_used.values():
        session.add(
            CutListPricingEntry(
                id=uuid4(), pricing_id=row_id, entry_id=entry.id, cents_used=entry.effective_cents
            )
        )
    session.flush()
    return pricing_row


def describe_pricing(session: Session, row: CutListPricing) -> dict[str, Any]:
    """A pricing as a plain dict: totals in cents, counts, completeness and every line.

    `version_approved` is read from the version now; the immutable record keeps nothing about it.
    """
    return {
        "id": str(row.id),
        "package_id": row.package_id,
        "version": row.version,
        "version_approved": version_approved(session, row.package_id, row.version),
        "store_key": row.store_key,
        "computed_at": row.computed_at.isoformat(),
        "materials_cents": row.materials_cents,
        "hardware_cents": row.hardware_cents,
        "banding_cents": row.banding_cents,
        "cut_service_cents": row.cut_service_cents,
        "delivery_cents": row.delivery_cents,
        "total_cents": row.total_cents,
        "complete": row.complete,
        "custom_count": row.custom_count,
        "undetermined_count": row.undetermined_count,
        "review_count": row.review_count,
        "unpriced_count": row.unpriced_count,
        "cut_charge_mode": row.cut_charge_mode,
        "result": row.result,
    }


def get_pricing(session: Session, pricing_id: UUID) -> CutListPricing:
    row = session.get(CutListPricing, pricing_id)
    if row is None:
        raise NotFound(f"there is no pricing {pricing_id}")
    return row


def list_pricings(session: Session, package_id: str, version: int | None = None) -> list[CutListPricing]:
    """Every pricing of a package (of one version when given), newest first."""
    from sqlalchemy import select

    statement = (
        select(CutListPricing)
        .where(CutListPricing.package_id == package_id)
        .order_by(CutListPricing.computed_at.desc())
    )
    if version is not None:
        statement = statement.where(CutListPricing.version == version)
    return list(session.scalars(statement))
