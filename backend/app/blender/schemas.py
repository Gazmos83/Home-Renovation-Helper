"""Pydantic-facing adapters for declarative Blender package specifications.

`CustomBuildSpec` is the one furniture contract: a document with a field it does
not define is refused naming that field (ladder step 2, CLAUDE.md §3). The room
scene's `output` names a kind only — the render tier decides frames, resolution
and engine (render-guard design decision 7).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_serializer,
    model_validator,
)

from app.blender.custom_build import derive as custom_derive
from app.blender.materials import panel_thickness_mm
from app.blender.room_contract import RoomBuildContext, normalise_room_scene
from app.blender.spec_contract import SpecValidationError

# --- custom builds (custom-build-packages) ----------------------------------------------
#
# Field shapes and ranges are ordinary Pydantic constraints, so a refusal names
# its field path. Relationships — slot references, overlap, front fit, the
# derived-row cap — are checked in one `model_validator` that raises
# `SpecValidationError` so a caller reports both kinds the same way. Every
# figure is a whole millimetre: the cut list's CSV contract carries integers.

MAX_DIMENSION_MM = 10_000
MAX_MODULES = 20
MAX_WALL_SHELVES = 20
MAX_DIVIDERS = 10
MAX_DERIVED_ROWS = 200

Millimetres = Annotated[int, Field(gt=0, le=MAX_DIMENSION_MM)]
Position = Annotated[int, Field(ge=0, le=MAX_DIMENSION_MM)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")]
SlotName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
Label = Annotated[str, StringConstraints(min_length=1, max_length=120)]
Note = Annotated[str, StringConstraints(max_length=500)]


class ResolvedFromIn(BaseModel):
    """What a slot said before the material review resolved it (material-review-on-import).

    Written by the review when a suggestion is applied; derivation marks every
    row of the slot with it, and a slot carrying it is not reviewed again.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    material: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    thickness_mm: Annotated[int, Field(gt=0, le=100)]
    lane: Literal["auto", "recommended", "chosen"]
    accepted_by: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    accepted_at: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class MaterialSlotIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    material: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    thickness_mm: Annotated[int, Field(gt=0, le=100)]
    resolved_from: ResolvedFromIn | None = None

    @model_serializer(mode="wrap")
    def _omit_unresolved(self, handler: Any) -> dict[str, Any]:
        # A slot the review never touched serialises exactly as before.
        dumped = handler(self)
        if dumped.get("resolved_from") is None:
            dumped.pop("resolved_from", None)
        return dumped


class HardwareLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
    item: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    qty: Annotated[int, Field(ge=1, le=10_000)]
    notes: Note = ""


class HandleIn(BaseModel):
    """A modelled handle on every leaf of one front entry (front-handles).

    Unstated fields take the defaults `derive.handle_spec` resolves, so a stored
    document keeps only what was written.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["bar", "knob"]
    length: Annotated[int, Field(ge=20, le=2000)] | None = None
    orientation: Literal["vertical", "horizontal"] | None = None
    edge: Literal["meeting", "left", "right"] | None = None
    inset_mm: Position | None = None
    at_mm: Position | None = None
    finish: Literal["black", "aluminium", "steel", "brass"] = "black"
    key: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")] | None = None

    @model_validator(mode="after")
    def _kind_fields(self) -> HandleIn:
        if self.kind == "bar" and self.length is None:
            raise ValueError("handle.length: a bar handle needs a length")
        if self.kind == "knob" and self.length is not None:
            raise ValueError("handle.length: a knob takes no length")
        if self.kind == "knob" and self.orientation is not None:
            raise ValueError("handle.orientation: a knob takes no orientation")
        return self

    @model_serializer(mode="wrap")
    def _omit_unstated(self, handler: Any) -> dict[str, Any]:
        dumped = handler(self)
        for field in ("length", "orientation", "edge", "inset_mm", "at_mm", "key"):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        return dumped


def _omit_unstated_handle(dumped: dict[str, Any]) -> dict[str, Any]:
    # A front without a handle serialises exactly as before.
    if dumped.get("handle") is None:
        dumped.pop("handle", None)
    return dumped


class SlatsIn(BaseModel):
    """Slats glued to the face of a door entry's leaves, spaced to follow the leaf (door-slats).

    Unstated optional fields are omitted on serialisation, so a stored document
    keeps only what was written; `derive.slat_layout` resolves the defaults.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    count: Annotated[int, Field(ge=1, le=40)]
    width: Millimetres
    material: SlotName
    orientation: Literal["vertical", "horizontal"] | None = None
    margin_mm: Annotated[int, Field(ge=0, le=500)] | None = None
    leaves: Annotated[list[Annotated[int, Field(ge=1, le=20)]], Field(min_length=1, max_length=20)] | None = None

    @model_serializer(mode="wrap")
    def _omit_unstated(self, handler: Any) -> dict[str, Any]:
        dumped = handler(self)
        for field in ("orientation", "margin_mm", "leaves"):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        return dumped


class DoorIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["door"]
    count: Annotated[int, Field(ge=1, le=20)]
    opening: Literal["hinge", "push_latch"]
    height: Millimetres | None = None
    hinge: Slug = "hinge-concealed-110"
    handle: HandleIn | None = None
    slats: SlatsIn | None = None
    # A door number (from 1 on the left) to its own material slot; unnamed doors keep the
    # carcass slot (door-leaf-materials).
    leaf_materials: (
        Annotated[dict[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]?$")], SlotName], Field(min_length=1)]
        | None
    ) = None

    @model_validator(mode="after")
    def _handle_fits_door(self) -> DoorIn:
        if self.handle is None:
            return self
        if self.opening == "push_latch":
            raise ValueError("handle: a push-latch door takes no handle")
        if self.handle.edge == "meeting" and self.count % 2:
            raise ValueError("handle.edge: meeting edges need an even number of doors")
        return self

    @model_validator(mode="after")
    def _slat_leaves(self) -> DoorIn:
        if self.slats is None or self.slats.leaves is None:
            return self
        leaves = self.slats.leaves
        if any(leaf > self.count for leaf in leaves):
            noun = "door" if self.count == 1 else "doors"
            raise ValueError(f"slats.leaves: the entry has {self.count} {noun}; number them 1 to {self.count}")
        if len(set(leaves)) != len(leaves):
            raise ValueError("slats.leaves: each door may be named once")
        return self

    @model_validator(mode="after")
    def _leaf_material_doors(self) -> DoorIn:
        if self.leaf_materials and any(int(door) > self.count for door in self.leaf_materials):
            noun = "door" if self.count == 1 else "doors"
            raise ValueError(f"leaf_materials: the entry has {self.count} {noun}; number them 1 to {self.count}")
        return self

    @model_serializer(mode="wrap")
    def _omit_handle(self, handler: Any) -> dict[str, Any]:
        dumped = _omit_unstated_handle(handler(self))
        # A door without slats serialises exactly as before.
        if dumped.get("slats") is None:
            dumped.pop("slats", None)
        if dumped.get("leaf_materials") is None:
            dumped.pop("leaf_materials", None)
        return dumped


class DrawerIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["drawer"]
    count: Annotated[int, Field(ge=1, le=20)]
    height: Millimetres | None = None
    handle: HandleIn | None = None

    @model_validator(mode="after")
    def _no_edge(self) -> DrawerIn:
        if self.handle is not None and self.handle.edge is not None:
            raise ValueError("handle.edge: only a door handle takes an edge; a drawer's sits on its top edge")
        return self

    @model_serializer(mode="wrap")
    def _omit_handle(self, handler: Any) -> dict[str, Any]:
        return _omit_unstated_handle(handler(self))


class FlapIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["flap"]
    hinged: Literal["bottom", "top"]
    height: Millimetres | None = None
    handle: HandleIn | None = None

    @model_validator(mode="after")
    def _no_edge(self) -> FlapIn:
        if self.handle is not None and self.handle.edge is not None:
            raise ValueError("handle.edge: only a door handle takes an edge; a flap's sits opposite its hinge")
        return self

    @model_serializer(mode="wrap")
    def _omit_handle(self, handler: Any) -> dict[str, Any]:
        return _omit_unstated_handle(handler(self))


FrontIn = Annotated[DoorIn | DrawerIn | FlapIn, Field(discriminator="type")]

SIDE_FOLDS_DESCRIPTION = (
    "carcass-side panel bends. Each: side left|right, from_mm, along height|depth, "
    "angle_deg 1-89, towards inside|outside. [] clears. A 26° left height bend from "
    '1100 mm is [{"side": "left", "from_mm": 1100, "along": "height", '
    '"angle_deg": 26, "towards": "inside"}].'
)


class SideFoldIn(BaseModel):
    """One kink on a carcass side: the named face runs straight to `from_mm`, then leaves its plane."""

    model_config = ConfigDict(extra="forbid", strict=True)

    side: Literal["left", "right"] = Field(description="which carcass side folds")
    from_mm: Millimetres = Field(description="kink from the bottom face, or from the front face when along is depth")
    along: Literal["height", "depth"] = Field(
        description="height: from_mm from the bottom; depth: from_mm from the front"
    )
    angle_deg: Annotated[int, Field(ge=1, le=89, description="bend angle in degrees from the original axis")]
    towards: Literal["inside", "outside"] = Field(
        description="inside moves toward the opposite side after the kink"
    )


DIVIDER_SPANS_DESCRIPTION = (
    "where each divider stands and reaches, one per divider, left to right: from_board \"bottom\" or a shelf "
    "number, to_board \"top\" or a shelf number; shelves count from the lowest, fixed and adjustable together, "
    "and only a fixed shelf can hold a divider. [] clears (full height). A divider from the top of 4 shelves to "
    'the top is [{"from_board": 4, "to_board": "top"}].'
)
SHELF_KINDS_DESCRIPTION = (
    "each shelf's kind, lowest first, \"fixed\" or \"adjustable\", agreeing with shelves and "
    "adjustable_shelves; without it the fixed shelves are the lowest. [] clears."
)
SHELF_DEPTHS_DESCRIPTION = (
    "each shelf's cut depth in mm, lowest first (fixed and adjustable together), or null for the "
    "module's back-reduced depth; [] clears. Second shelf 500 mm: [null, 500, null, null]."
)
SHELF_DEPTH_ALIGN_DESCRIPTION = (
    '"back" (default): shelf rear on the carcass inner rear; "front": shelf front on the side fronts. '
    "Only with shelf_depths_mm."
)
MIN_SHELF_DEPTH_MM = 50

ShelfNumber = Annotated[int, Field(ge=1, le=40)]
ShelfKind = Literal["fixed", "adjustable"]
ShelfDepthAlign = Literal["back", "front"]
Mounting = Literal["floor", "wall"]
MOUNTING_DESCRIPTION = (
    "How the module is fixed: `floor` (standing) or `wall` (hung on the wall). "
    "Leave it out when not stated; it changes no cut list, hardware or model."
)
ShelfDepthEntry = Millimetres | None


HANGING_RAILS_DESCRIPTION = (
    "Clothes rails hung across a bay (hardware-catalog). `z` is the rail centre in mm above the top of "
    "the bottom panel and is required; `bay` counts from 1 on the left; `inset_y_mm` is from the front "
    "of the sides (default half the inner depth). The rail is cut to the bay's inner width and gets two "
    "end supports; both are drawn and listed, so they are not also written as hardware lines."
)
MAX_HANGING_RAILS = 4


class HangingRailIn(BaseModel):
    """One clothes rail across a bay, with its end supports (hardware-catalog)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    bay: Annotated[int, Field(ge=1, le=MAX_DIVIDERS + 1)] = 1
    z: Millimetres
    inset_y_mm: Millimetres | None = None
    finish: Literal["black", "aluminium", "steel", "brass", "nickel", "chrome"] | None = None
    key: Slug | None = None
    support_key: Slug | None = None

    @model_serializer(mode="wrap")
    def _omit_unstated(self, handler: Any) -> dict[str, Any]:
        dumped = handler(self)
        for field in ("inset_y_mm", "finish", "key", "support_key"):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        return dumped


class DividerSpanIn(BaseModel):
    """The two boards one divider runs between: the bottom panel or a shelf, and a shelf or the top panel."""

    model_config = ConfigDict(extra="forbid", strict=True)

    from_board: Literal["bottom"] | ShelfNumber = Field(
        description='"bottom", or the number of the fixed shelf the divider stands on, counted from the lowest'
    )
    to_board: Literal["top"] | ShelfNumber = Field(
        description='"top", or the number of the fixed shelf the divider reaches, counted from the lowest'
    )


class ModuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Slug
    name: Label
    x: Position
    y: Position
    z: Position
    width: Millimetres
    height: Millimetres
    depth: Millimetres
    carcass: SlotName
    back: SlotName | None = None
    shelves: Annotated[int, Field(ge=0, le=20)] = 0
    adjustable_shelves: Annotated[int, Field(ge=0, le=20)] = 0
    shelf_pin: Slug = "shelf-pin"
    shelf_spacing_mm: Millimetres | None = None
    shelf_positions_mm: Annotated[list[Position], Field(min_length=1, max_length=40)] | None = None
    dividers: Annotated[int, Field(ge=0, le=MAX_DIVIDERS)] = 0
    divider_positions_mm: Annotated[list[Position], Field(min_length=1, max_length=MAX_DIVIDERS)] | None = None
    divider_spans: Annotated[
        list[DividerSpanIn], Field(min_length=1, max_length=MAX_DIVIDERS, description=DIVIDER_SPANS_DESCRIPTION)
    ] | None = None
    shelf_kinds: Annotated[
        list[ShelfKind], Field(min_length=1, max_length=40, description=SHELF_KINDS_DESCRIPTION)
    ] | None = None
    shelf_depths_mm: Annotated[
        list[ShelfDepthEntry], Field(min_length=1, max_length=40, description=SHELF_DEPTHS_DESCRIPTION)
    ] | None = None
    shelf_depth_align: Annotated[ShelfDepthAlign, Field(description=SHELF_DEPTH_ALIGN_DESCRIPTION)] | None = None
    side_folds: Annotated[list[SideFoldIn], Field(max_length=2, description=SIDE_FOLDS_DESCRIPTION)] = []
    hanging_rails: Annotated[
        list[HangingRailIn], Field(max_length=MAX_HANGING_RAILS, description=HANGING_RAILS_DESCRIPTION)
    ] = []
    mounting: Annotated[Mounting, Field(description=MOUNTING_DESCRIPTION)] | None = None
    fronts: Annotated[list[FrontIn], Field(max_length=10)] = []
    hardware: Annotated[list[HardwareLineIn], Field(max_length=50)] = []

    @model_validator(mode="after")
    def _default_shelf_depth_align(self) -> ModuleIn:
        if self.shelf_depths_mm is not None and self.shelf_depth_align is None:
            return self.model_copy(update={"shelf_depth_align": "back"})
        return self

    @model_serializer(mode="wrap")
    def _omit_unstated_interior(self, handler: Any) -> dict[str, Any]:
        # A module without spacing, positions, dividers or folds serialises exactly as before.
        dumped = handler(self)
        for field in (
            "shelf_spacing_mm",
            "shelf_positions_mm",
            "divider_positions_mm",
            "divider_spans",
            "shelf_kinds",
            "shelf_depths_mm",
            "shelf_depth_align",
            "mounting",
        ):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        if not dumped.get("dividers"):
            dumped.pop("dividers", None)
        if not dumped.get("side_folds"):
            dumped.pop("side_folds", None)
        if not dumped.get("hanging_rails"):
            dumped.pop("hanging_rails", None)
        return dumped


class WallShelfIn(BaseModel):
    """A board hung on brackets. Its bracket count and positions are calculated unless the owner sets them."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: Slug
    name: Label
    x: Position
    y: Position = 0
    z: Position
    length: Millimetres
    depth: Millimetres
    material: SlotName
    bracket: Slug
    bracket_positions_mm: Annotated[list[Position], Field(min_length=1, max_length=20)] | None = None


Axis = Literal["x", "y", "z"]
TurnDegrees = Annotated[int, Field(ge=-89, le=89)]


class ExtraTiltIn(BaseModel):
    """The piece's length turns towards `towards` by `angle_deg`, positive towards that axis's positive direction."""

    model_config = ConfigDict(extra="forbid", strict=True)

    towards: Axis
    angle_deg: TurnDegrees

    @model_validator(mode="after")
    def _not_zero(self) -> ExtraTiltIn:
        if self.angle_deg == 0:
            raise ValueError("angle_deg: state a tilt other than 0, or leave tilt out")
        return self


class ExtraPlacementIn(BaseModel):
    """Where one extra-part piece sits: its reference corner, its axes, then an optional roll and tilt."""

    model_config = ConfigDict(extra="forbid", strict=True)

    x: Position
    y: Position
    z: Position
    length_along: Axis
    width_along: Axis
    roll_deg: TurnDegrees | None = None
    tilt: ExtraTiltIn | None = None

    @model_validator(mode="after")
    def _axes(self) -> ExtraPlacementIn:
        if self.length_along == self.width_along:
            raise ValueError("width_along: must differ from length_along")
        if self.roll_deg == 0:
            raise ValueError("roll_deg: state a roll other than 0, or leave roll_deg out")
        if self.tilt is not None and self.tilt.towards == self.length_along:
            raise ValueError("tilt.towards: must differ from length_along")
        return self

    @model_serializer(mode="wrap")
    def _omit_unstated_turns(self, handler: Any) -> dict[str, Any]:
        dumped = handler(self)
        for field in ("roll_deg", "tilt"):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        return dumped


class ExtraEndCutsIn(BaseModel):
    """Each end's cut from square; positive shortens the edge opposite the reference edge."""

    model_config = ConfigDict(extra="forbid", strict=True)

    across: Literal["width", "thickness"]
    start_deg: TurnDegrees
    end_deg: TurnDegrees


class ExtraPartIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Slug
    name: Label
    qty: Annotated[int, Field(ge=1, le=100)]
    length: Millimetres
    width: Millimetres
    material: SlotName
    grain: Literal["length", "none"] = "length"
    notes: Note = ""
    hardware: Annotated[list[HardwareLineIn], Field(max_length=50)] = []
    supply: Literal["Personal_Supply"] | None = None
    placements: Annotated[list[ExtraPlacementIn], Field(max_length=100)] | None = None
    end_cuts: ExtraEndCutsIn | None = None

    @model_serializer(mode="wrap")
    def _omit_unplaced(self, handler: Any) -> dict[str, Any]:
        # An extra part without placements or end cuts serialises exactly as before.
        dumped = handler(self)
        for field in ("placements", "end_cuts"):
            if dumped.get(field) is None:
                dumped.pop(field, None)
        return dumped


class PartOverrideIn(BaseModel):
    """The workshop's correction of one derived cut-list row, applied after every rule."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")]
    qty: Annotated[int, Field(ge=1, le=10_000)] | None = None
    length: Millimetres | None = None
    width: Millimetres | None = None
    thickness: Annotated[int, Field(gt=0, le=100)] | None = None
    material: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    banding: Annotated[str, StringConstraints(min_length=1, max_length=60)] | None = None
    notes: Note | None = None
    supply: Literal["Personal_Supply"] | None = None


class EnvelopeIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    width: Millimetres
    height: Millimetres
    depth: Millimetres


@dataclass(frozen=True)
class CustomBuildContext:
    """What a caller outside the derivation needs: the build's overall size."""

    overall: dict[str, int]


def _check_hanging_rails(where: str, module: ModuleIn, t: int, b: int) -> None:
    """Each rail in an existing bay, clear of the shelves, below the board above by the hook clearance."""
    if not module.hanging_rails:
        return
    dumped = module.model_dump(mode="json")
    for index in range(len(module.hanging_rails)):
        problem = custom_derive.hanging_rail_problem(dumped, t, b, index)
        if problem is not None:
            field, reason = problem
            raise SpecValidationError(f"{where}.hanging_rails[{index}].{field}: {reason}")


def _check_interior(where: str, module: ModuleIn, t: int, b: int = 0) -> None:
    """Shelf spacing or positions and dividers against the module's inner height and width."""
    count = module.shelves + module.adjustable_shelves
    spacing, positions = module.shelf_spacing_mm, module.shelf_positions_mm
    if spacing is not None and positions is not None:
        raise SpecValidationError(
            f"{where}: shelf_spacing_mm and shelf_positions_mm cannot both be given; state one"
        )
    field = "shelf_spacing_mm" if spacing is not None else "shelf_positions_mm"
    if module.divider_spans is not None and not module.dividers:
        raise SpecValidationError(f"{where}.divider_spans: module {module.id!r} has no dividers")
    if module.shelf_kinds is not None and not count:
        raise SpecValidationError(f"{where}.shelf_kinds: module {module.id!r} has no shelves")
    if (spacing is not None or positions is not None) and not count:
        raise SpecValidationError(f"{where}.{field}: module {module.id!r} has no shelves to place")
    if positions is not None:
        if len(positions) != count:
            raise SpecValidationError(
                f"{where}.shelf_positions_mm: {len(positions)} positions given, {count} shelves expected "
                "(fixed and adjustable together)"
            )
        if any(later - earlier < t for earlier, later in pairwise(positions)):
            raise SpecValidationError(
                f"{where}.shelf_positions_mm: positions must increase by at least the board thickness ({t} mm)"
            )
    if spacing is not None or positions is not None:
        inner_h = module.height - 2 * t
        top = custom_derive.shelf_undersides(module.model_dump(mode="json"), t)[-1] + t
        if top > inner_h:
            raise SpecValidationError(
                f"{where}.{field}: the top shelf's top face at {top:g} mm is above the inner height of "
                f"{inner_h} mm (measured from the top face of the bottom panel)"
            )

    inner_w = module.width - 2 * t
    dividers, places = module.dividers, module.divider_positions_mm
    if places is not None:
        if len(places) != dividers:
            raise SpecValidationError(
                f"{where}.divider_positions_mm: {len(places)} positions given, {dividers} dividers expected"
            )
        if any(later - earlier <= t for earlier, later in pairwise(places)):
            raise SpecValidationError(
                f"{where}.divider_positions_mm: positions must increase by more than the board thickness ({t} mm)"
            )
        if places[0] <= 0 or places[-1] + t >= inner_w:
            raise SpecValidationError(
                f"{where}.divider_positions_mm: every divider must lie inside the inner width of {inner_w} mm "
                "with a bay on each side (measured from the left side's inner face)"
            )
    elif dividers and (inner_w - dividers * t) // (dividers + 1) <= 0:
        raise SpecValidationError(
            f"{where}.dividers: {dividers} dividers leave no room for a bay in the inner width of {inner_w} mm"
        )

    kinds = module.shelf_kinds
    if kinds is not None:
        fixed = sum(1 for kind in kinds if kind == "fixed")
        if len(kinds) != count or fixed != module.shelves:
            raise SpecValidationError(
                f"{where}.shelf_kinds: {fixed} fixed and {len(kinds) - fixed} adjustable listed, but the module has "
                f"{module.shelves} fixed and {module.adjustable_shelves} adjustable shelves"
            )

    _check_shelf_depths(where, module, t, b)

    spans = module.divider_spans
    if spans is None:
        return
    if len(spans) != dividers:
        raise SpecValidationError(f"{where}.divider_spans: {len(spans)} spans given, {dividers} dividers expected")
    kind_of = custom_derive.shelf_kinds_of(module.model_dump(mode="json"))
    for number, span in enumerate(spans, start=1):
        for board in (span.from_board, span.to_board):
            if isinstance(board, str):
                continue
            if board > count:
                raise SpecValidationError(
                    f"{where}.divider_spans: divider {number} names shelf {board}, but the module has {count} shelves"
                )
            if kind_of[board - 1] != "fixed":
                raise SpecValidationError(
                    f"{where}.divider_spans: divider {number} names shelf {board}, which is adjustable; "
                    "only a fixed shelf can hold a divider"
                )
        low = 0 if span.from_board == "bottom" else span.from_board
        high = count + 1 if span.to_board == "top" else span.to_board
        if low >= high:
            raise SpecValidationError(
                f"{where}.divider_spans: divider {number} must stand on a board below the one it reaches"
            )


def _check_shelf_depths(where: str, module: ModuleIn, t: int, b: int) -> None:
    """Per-shelf depths and align against the shelf count, minimum depth and folded inner depth."""
    depths, align = module.shelf_depths_mm, module.shelf_depth_align
    if align is not None and depths is None:
        raise SpecValidationError(f"{where}.shelf_depth_align: shelf_depths_mm must be set when an align is given")
    if depths is None:
        return
    count = module.shelves + module.adjustable_shelves
    if not count:
        raise SpecValidationError(f"{where}.shelf_depths_mm: module {module.id!r} has no shelves")
    if len(depths) != count:
        raise SpecValidationError(
            f"{where}.shelf_depths_mm: {len(depths)} depths given, {count} shelves expected "
            "(fixed and adjustable together)"
        )
    for index, depth in enumerate(depths, start=1):
        if depth is not None and depth < MIN_SHELF_DEPTH_MM:
            raise SpecValidationError(
                f"{where}.shelf_depths_mm: shelf {index} depth {depth} mm is below the minimum of "
                f"{MIN_SHELF_DEPTH_MM} mm"
            )
    document = module.model_dump(mode="json")
    # A back-aligned board deeper than the folded inner depth sticks out the front, past the folds;
    # only a front-aligned one would pass through the back (auto-fit-protruding-shelves).
    if module.side_folds and custom_derive.shelf_depth_align_of(document) == "front":
        profile = custom_derive.fold_profile(document, t, b)
        available = profile.inner_d
        for level, depth in enumerate(depths, start=1):
            if depth is not None and depth > available:
                raise SpecValidationError(
                    f"{where}.shelf_depths_mm: shelf {level} depth {depth} mm exceeds the folded inner depth "
                    f"of {available} mm along that board"
                )


def _module_aabb(module: ModuleIn, t: int, b: int) -> tuple[int, int, int, int, int, int]:
    """The folded solid's AABB in build millimetres: (x, y, z, w, d, h)."""
    x0, y0, z0, w, d, h = custom_derive.module_bounds(module.model_dump(mode="json"), t, b)
    return module.x + x0, module.y + y0, module.z + z0, w, d, h


def _aabbs_overlap(
    a: tuple[int, int, int, int, int, int], b: tuple[int, int, int, int, int, int]
) -> bool:
    """True when two AABBs share volume; touching faces do not count."""
    ax, ay, az, aw, ad, ah = a
    bx, by, bz, bw, bd, bh = b
    return (
        ax < bx + bw
        and bx < ax + aw
        and ay < by + bd
        and by < ay + ad
        and az < bz + bh
        and bz < az + ah
    )


def _boxes_overlap(a: ModuleIn, b: ModuleIn, t_a: int, b_a: int, t_b: int, b_b: int) -> bool:
    """True when two modules' folded bounding boxes share volume; touching faces do not count."""
    return _aabbs_overlap(_module_aabb(a, t_a, b_a), _module_aabb(b, t_b, b_b))


def _check_folds(where: str, module: ModuleIn, t: int, b: int) -> None:
    """A folded module's geometry uses fold_profile; its dividers must fit inside the folded opening."""
    if not module.side_folds:
        return
    try:
        custom_derive.fold_profile(module.model_dump(mode="json"), t, b)
    except custom_derive.DeriveError as error:
        raise SpecValidationError(f"{where}.side_folds: {error}") from None


def _check_folded_dividers(where: str, module: ModuleIn, t: int, b: int) -> None:
    """Every divider on a folded module lies inside the folded opening along its whole span."""
    if not module.side_folds or not module.dividers:
        return
    problem = custom_derive.divider_fit_problem(module.model_dump(mode="json"), t, b)
    if problem:
        field = "divider_positions_mm" if module.divider_positions_mm else "dividers"
        raise SpecValidationError(f"{where}.{field}: {problem}")


class CustomBuildSpec(BaseModel):
    """A declarative build of positioned modules; see `custom_build.derive` for the rules."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["custom_build"]
    schema_version: Literal[1]
    units: Literal["mm"]
    name: Label
    template: Slug | None = None
    materials: dict[SlotName, MaterialSlotIn] = {}
    envelope: EnvelopeIn | None = None
    modules: Annotated[list[ModuleIn], Field(max_length=MAX_MODULES)] = []
    extra_parts: Annotated[list[ExtraPartIn], Field(max_length=100)] = []
    wall_shelves: Annotated[list[WallShelfIn], Field(max_length=MAX_WALL_SHELVES)] = []
    hardware: Annotated[list[HardwareLineIn], Field(max_length=100)] = []
    assembly_notes: Annotated[list[Note], Field(max_length=20)] = []
    part_overrides: Annotated[list[PartOverrideIn], Field(max_length=MAX_DERIVED_ROWS)] = []

    @model_validator(mode="after")
    def _validate_relationships(self) -> CustomBuildSpec:
        # A string the normaliser cannot read (`unknown:`) is accepted and
        # left for the material review (material-review-on-import); a sheet
        # string must still agree with its slot's thickness.
        for slot, entry in self.materials.items():
            stated = panel_thickness_mm(entry.material)
            if stated is not None and stated != entry.thickness_mm:
                raise SpecValidationError(
                    f"materials.{slot}.thickness_mm: {entry.thickness_mm} does not match the "
                    f"thickness named in {entry.material!r}"
                )

        seen: set[str] = set()
        for index, module in enumerate(self.modules):
            where = f"modules[{index}]"
            if module.id in seen:
                raise SpecValidationError(f"{where}.id: duplicate module id {module.id!r}")
            seen.add(module.id)
            for field in ("carcass", "back"):
                slot = getattr(module, field)
                if slot is not None and slot not in self.materials:
                    raise SpecValidationError(f"{where}.{field}: undefined material slot {slot!r}")
            t = self.materials[module.carcass].thickness_mm
            if module.width <= 2 * t:
                raise SpecValidationError(
                    f"{where}.width: must be larger than twice the carcass thickness ({2 * t} mm)"
                )
            if module.height <= 2 * t:
                raise SpecValidationError(
                    f"{where}.height: must be larger than twice the carcass thickness ({2 * t} mm)"
                )
            b = self.materials[module.back].thickness_mm if module.back is not None else 0
            if module.depth <= b:
                raise SpecValidationError(f"{where}.depth: must be larger than the back thickness ({b} mm)")
            _check_folds(where, module, t, b)
            if self.envelope is not None:
                mx, my, mz, mw, md, mh = _module_aabb(module, t, b)
                if (
                    mx < 0
                    or my < 0
                    or mz < 0
                    or mx + mw > self.envelope.width
                    or mz + mh > self.envelope.height
                    or my + md > self.envelope.depth
                ):
                    raise SpecValidationError(f"{where}: module {module.id!r} lies outside the envelope")
            self._check_fronts(where, module, t, b)
            _check_interior(where, module, t, b)
            _check_hanging_rails(where, module, t, b)
            _check_folded_dividers(where, module, t, b)

        for index, part in enumerate(self.extra_parts):
            if part.material not in self.materials:
                raise SpecValidationError(
                    f"extra_parts[{index}].material: undefined material slot {part.material!r}"
                )
            self._check_extra_part(index, part)

        self._check_wall_shelves(seen)

        boxes = []
        for module in self.modules:
            t = self.materials[module.carcass].thickness_mm
            b = self.materials[module.back].thickness_mm if module.back is not None else 0
            boxes.append((module, t, b))
        for i, (first, t_a, b_a) in enumerate(boxes):
            for second, t_b, b_b in boxes[i + 1 :]:
                if _boxes_overlap(first, second, t_a, b_a, t_b, b_b):
                    raise SpecValidationError(
                        f"modules: {first.id!r} and {second.id!r} overlap"
                    )

        if not self.modules and self.envelope is None:
            raise SpecValidationError("envelope: a build with no modules needs an envelope")

        parts = custom_derive.base_parts(self.model_dump(mode="json"))
        if len(parts) > MAX_DERIVED_ROWS:
            raise SpecValidationError(
                f"modules: the build derives {len(parts)} cut-list rows; at most {MAX_DERIVED_ROWS} are allowed"
            )
        ids: set[str] = set()
        for part in parts:
            if part["id"] in ids:
                raise SpecValidationError(f"extra_parts: part id {part['id']!r} is used twice")
            ids.add(part["id"])

        overridden: set[str] = set()
        for index, override in enumerate(self.part_overrides):
            where = f"part_overrides[{index}]"
            if override.id not in ids:
                raise SpecValidationError(f"{where}.id: no derived cut-list row is named {override.id!r}")
            if override.id in overridden:
                raise SpecValidationError(f"{where}.id: row {override.id!r} is overridden twice")
            overridden.add(override.id)
        return self

    def _check_extra_part(self, index: int, part: ExtraPartIn) -> None:
        where = f"extra_parts[{index}]"
        thickness = self.materials[part.material].thickness_mm
        document = part.model_dump(mode="json")
        if part.end_cuts is not None and min(custom_derive.end_cut_edges(document, thickness)) <= 0:
            raise SpecValidationError(f"{where}.end_cuts: the end cuts leave no length on part {part.id!r}")
        if part.placements is None:
            return
        if len(part.placements) != part.qty:
            raise SpecValidationError(
                f"{where}.placements: {part.qty} are needed, one per piece, but {len(part.placements)} "
                f"are given for part {part.id!r}"
            )
        if self.envelope is None:
            return
        limits = (self.envelope.width, self.envelope.depth, self.envelope.height)
        for placement in document["placements"]:
            for corner in custom_derive.extra_piece_corners(document, placement, thickness):
                if any(value < -1e-6 or value > limit + 1e-6 for value, limit in zip(corner, limits, strict=True)):
                    raise SpecValidationError(f"{where}: part {part.id!r} lies outside the envelope")

    def _check_wall_shelves(self, module_ids: set[str]) -> None:
        taken = module_ids | {part.id for part in self.extra_parts}
        for index, shelf in enumerate(self.wall_shelves):
            where = f"wall_shelves[{index}]"
            if shelf.id in taken:
                raise SpecValidationError(f"{where}.id: {shelf.id!r} is already used by a module, part or shelf")
            taken.add(shelf.id)
            if shelf.material not in self.materials:
                raise SpecValidationError(f"{where}.material: undefined material slot {shelf.material!r}")
            thickness = self.materials[shelf.material].thickness_mm
            if self.envelope is not None and (
                shelf.x + shelf.length > self.envelope.width
                or shelf.z + thickness > self.envelope.height
                or shelf.y + shelf.depth > self.envelope.depth
            ):
                raise SpecValidationError(f"{where}: shelf {shelf.id!r} lies outside the envelope")
            positions = shelf.bracket_positions_mm
            if positions is None:
                continue
            if any(position <= 0 or position >= shelf.length for position in positions):
                raise SpecValidationError(
                    f"{where}.bracket_positions_mm: every position must lie inside the board "
                    f"(0 to {shelf.length} mm)"
                )
            if any(later <= earlier for earlier, later in pairwise(positions)):
                raise SpecValidationError(f"{where}.bracket_positions_mm: positions must be strictly increasing")

    def _check_fronts(self, where: str, module: ModuleIn, t: int, b: int) -> None:
        document = module.model_dump(mode="json")
        try:
            rects = custom_derive.front_layout(document, t, b)
        except custom_derive.DeriveError as error:
            raise SpecValidationError(f"{where}.fronts: {error}") from None
        minimum = custom_derive.MIN_FRONT_MM
        profile = (
            custom_derive.fold_profile(document, t, b) if module.side_folds else None
        )
        for index, front in enumerate(module.fronts):
            entry = [rect for rect in rects if rect["entry"] == index]
            if any(rect["w"] < minimum or rect["h"] < minimum for rect in entry):
                count = getattr(front, "count", 1)
                raise SpecValidationError(
                    f"{where}.fronts[{index}]: {count} {front.type} front(s) do not fit module "
                    f"{module.id!r} at the minimum front size of {minimum} mm"
                )
            if front.type == "drawer":
                if custom_derive.runner_length(module.depth - b) is None:
                    raise SpecValidationError(
                        f"{where}.fronts[{index}]: module {module.id!r} is too shallow for a drawer runner"
                    )
                for rect in entry:
                    inner = module.width - 2 * t
                    if profile is not None:
                        inner = custom_derive.min_inner_width(
                            profile, 0, profile.inner_d, rect["z"], rect["z"] + rect["h"]
                        )
                    box_back = inner - 2 * custom_derive.DRAWER_SIDE_CLEARANCE_MM - 2 * t
                    if box_back <= 0:
                        raise SpecValidationError(
                            f"{where}.fronts[{index}]: module {module.id!r} is too narrow for a drawer box"
                        )
        for index, front in enumerate(module.fronts):
            if front.handle is not None and module.side_folds:
                raise SpecValidationError(
                    f"{where}.fronts[{index}].handle: handles on a folded module are not supported"
                )
            leaf_materials = getattr(front, "leaf_materials", None) or {}
            for slot in leaf_materials.values():
                if slot not in self.materials:
                    raise SpecValidationError(
                        f"{where}.fronts[{index}].leaf_materials: undefined material slot {slot!r}"
                    )
                if self.materials[slot].thickness_mm != t:
                    raise SpecValidationError(
                        f"{where}.fronts[{index}].leaf_materials: slot {slot!r} is "
                        f"{self.materials[slot].thickness_mm:g} mm but the carcass is {t:g} mm; "
                        "a door must be as thick as the carcass"
                    )
            if leaf_materials and module.side_folds:
                raise SpecValidationError(
                    f"{where}.fronts[{index}].leaf_materials: per-door materials on a folded module are not supported"
                )
            slats = getattr(front, "slats", None)
            if slats is None:
                continue
            if slats.material not in self.materials:
                raise SpecValidationError(
                    f"{where}.fronts[{index}].slats.material: undefined material slot {slats.material!r}"
                )
            if module.side_folds:
                raise SpecValidationError(
                    f"{where}.fronts[{index}].slats: slats on a folded module are not supported"
                )
        try:
            custom_derive.handle_layout(document, t, b)
            custom_derive.slat_layout(document, self.model_dump(mode="json")["materials"], t, b)
        except custom_derive.DeriveError as error:
            raise SpecValidationError(f"{where}.{error}") from None

    @property
    def context(self) -> CustomBuildContext:
        return CustomBuildContext(overall=custom_derive.overall(self.model_dump(mode="json")))


class ModuleChange(BaseModel):
    """Every `ModuleIn` field but its id, each optional; an absent field keeps its value."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Label | None = None
    x: Position | None = None
    y: Position | None = None
    z: Position | None = None
    width: Millimetres | None = None
    height: Millimetres | None = None
    depth: Millimetres | None = None
    carcass: SlotName | None = None
    back: SlotName | None = None
    shelves: Annotated[int, Field(ge=0, le=20)] | None = None
    adjustable_shelves: Annotated[int, Field(ge=0, le=20)] | None = None
    shelf_pin: Slug | None = None
    # 0 or an empty list clears the field: even spacing, or equal bays.
    shelf_spacing_mm: Annotated[int, Field(ge=0, le=MAX_DIMENSION_MM)] | None = None
    shelf_positions_mm: Annotated[list[Position], Field(max_length=40)] | None = None
    dividers: Annotated[int, Field(ge=0, le=MAX_DIVIDERS)] | None = None
    divider_positions_mm: Annotated[list[Position], Field(max_length=MAX_DIVIDERS)] | None = None
    divider_spans: Annotated[
        list[DividerSpanIn], Field(max_length=MAX_DIVIDERS, description=DIVIDER_SPANS_DESCRIPTION)
    ] | None = None
    shelf_kinds: Annotated[list[ShelfKind], Field(max_length=40, description=SHELF_KINDS_DESCRIPTION)] | None = None
    shelf_depths_mm: Annotated[
        list[ShelfDepthEntry], Field(max_length=40, description=SHELF_DEPTHS_DESCRIPTION)
    ] | None = None
    shelf_depth_align: Annotated[ShelfDepthAlign, Field(description=SHELF_DEPTH_ALIGN_DESCRIPTION)] | None = None
    side_folds: Annotated[list[SideFoldIn], Field(max_length=2, description=SIDE_FOLDS_DESCRIPTION)] | None = None
    # A whole new list of rails; `[]` removes every rail.
    hanging_rails: Annotated[
        list[HangingRailIn], Field(max_length=MAX_HANGING_RAILS, description=HANGING_RAILS_DESCRIPTION)
    ] | None = None
    # "unset" clears it back to not stated.
    mounting: Annotated[
        Mounting | Literal["unset"], Field(description=MOUNTING_DESCRIPTION + ' "unset" clears it.')
    ] | None = None
    hinge: Slug | None = None  # sets the hinge item of every hinged door in the module
    fronts: Annotated[list[FrontIn], Field(max_length=10)] | None = None
    hardware: Annotated[list[HardwareLineIn], Field(max_length=50)] | None = None


class WallShelfChange(BaseModel):
    """Every `WallShelfIn` field but its id, each optional; an absent field keeps its value.

    An empty `bracket_positions_mm` clears the owner's positions, so the brackets are calculated again.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Label | None = None
    x: Position | None = None
    y: Position | None = None
    z: Position | None = None
    length: Millimetres | None = None
    depth: Millimetres | None = None
    material: SlotName | None = None
    bracket: Slug | None = None
    bracket_positions_mm: Annotated[list[Position], Field(max_length=20)] | None = None


class ExtraPartChange(BaseModel):
    """Where an existing extra part's pieces sit, and how its ends are cut; at least one.

    An empty `placements` unplaces the part, so it is laid beside the build again;
    `end_cuts` of 0° at both ends makes the ends square again.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    placements: Annotated[list[ExtraPlacementIn], Field(max_length=100)] | None = None
    end_cuts: ExtraEndCutsIn | None = None


class PackageChanges(BaseModel):
    """A bounded set of changes to a stored `custom_build`; at least one."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Label | None = None
    envelope: EnvelopeIn | None = None
    materials: dict[SlotName, MaterialSlotIn] = {}
    modules: dict[Slug, ModuleChange] = {}
    add_modules: Annotated[list[ModuleIn], Field(max_length=MAX_MODULES)] = []
    remove_modules: Annotated[list[Slug], Field(max_length=MAX_MODULES)] = []
    add_extra_parts: Annotated[list[ExtraPartIn], Field(max_length=100)] = []
    remove_extra_parts: Annotated[list[Slug], Field(max_length=100)] = []
    extra_parts: dict[Slug, ExtraPartChange] = {}
    add_wall_shelves: Annotated[list[WallShelfIn], Field(max_length=MAX_WALL_SHELVES)] = []
    remove_wall_shelves: Annotated[list[Slug], Field(max_length=MAX_WALL_SHELVES)] = []
    wall_shelves: dict[Slug, WallShelfChange] = {}
    part_overrides: Annotated[list[PartOverrideIn], Field(max_length=MAX_DERIVED_ROWS)] = []

    @model_validator(mode="after")
    def _at_least_one(self) -> PackageChanges:
        if not any(
            (
                self.name is not None,
                self.envelope is not None,
                self.materials,
                self.modules,
                self.add_modules,
                self.remove_modules,
                self.add_extra_parts,
                self.remove_extra_parts,
                self.extra_parts,
                self.add_wall_shelves,
                self.remove_wall_shelves,
                self.wall_shelves,
                self.part_overrides,
            )
        ):
            raise ValueError("state at least one change")
        for slug, change in self.modules.items():
            if not change.model_dump(exclude_none=True):
                raise ValueError(f"modules.{slug}: state at least one field to change")
        for slug, part_change in self.extra_parts.items():
            if not part_change.model_dump(exclude_none=True):
                raise ValueError(f"extra_parts.{slug}: state placements or end_cuts to change")
        for slug, shelf_change in self.wall_shelves.items():
            if not shelf_change.model_dump(exclude_none=True):
                raise ValueError(f"wall_shelves.{slug}: state at least one field to change")
        return self


# --- room scenes (Tier 2 day 5) -------------------------------------------------------
#
# Unlike `ListeningWallSpec`, a room document cannot validate its own
# relationships alone: whether the package fits a wall depends on the
# package's own overall dimensions, which are not part of this document.
# `RoomSceneSpec` therefore only enforces the document's own shape (types,
# literals, no unknown field) through ordinary Pydantic validation; call
# `.context(package_overall)` to run the full relational check
# (`room_contract.normalise_room_scene`), which can raise
# `room_contract.SpecValidationError` - not wrapped into a `ValidationError`,
# since it happens outside the Pydantic validation lifecycle. A caller
# refusing bad input catches both exceptions.


class OpeningIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    wall: int
    type: Literal["door", "window"]
    offset_mm: int | float
    width_mm: int | float
    height_mm: int | float
    sill_mm: int | float = 0


class PlacementIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    wall: int
    offset_mm: int | float


class FurnishingIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    width_mm: int | float
    depth_mm: int | float
    height_mm: int | float
    x_mm: int | float
    y_mm: int | float
    rotation_deg: int | float
    z_mm: int | float = 0


class RoomIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    corners: list[list[int | float]]
    height_mm: int | float
    wall_thickness_mm: int | float = 100


class StillOutputIn(BaseModel):
    """A still. No resolution: the render tier decides it."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["still"]


class TurntableOutputIn(BaseModel):
    """A turntable. No frame count or resolution: the render tier decides both,
    so a document naming `frames` or `resolution` is refused by field name."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["turntable"]


OutputIn = Annotated[StillOutputIn | TurntableOutputIn, Field(discriminator="kind")]


class RoomSceneSpec(BaseModel):
    """The room document's shape - see the module-level note on relational validation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["room_scene"]
    schema_version: Literal[1]
    units: Literal["mm"]
    room: RoomIn
    openings: list[OpeningIn] = []
    placement: PlacementIn
    furnishings: list[FurnishingIn] = []
    output: OutputIn

    def context(self, package_overall: Mapping[str, float]) -> RoomBuildContext:
        return normalise_room_scene(self.model_dump(mode="json"), package_overall=package_overall)




def describe_validation_error(error: Any) -> str:
    """A pydantic `ValidationError` reduced to one line naming what is wrong.

    `SpecValidationError`, raised inside a model's cross-field validator, is
    wrapped into a `ValidationError` by pydantic itself, so every refusal of a
    furniture document — an unknown field by name, a range, a relationship —
    surfaces through this one path.
    """
    parts = []
    for detail in error.errors():
        location = ".".join(str(item) for item in detail["loc"]) or "(root)"
        parts.append(f"{location}: {detail['msg']}")
    return "; ".join(parts)
