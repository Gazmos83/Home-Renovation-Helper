"""Pydantic-facing adapters for declarative Blender package specifications.

`CustomBuildSpec` is the one furniture contract: a document with a field it does
not define is refused naming that field (ladder step 2, CLAUDE.md §3). The room
scene's `output` names a kind only — the render tier decides frames, resolution
and engine (render-guard design decision 7).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


class DoorIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["door"]
    count: Annotated[int, Field(ge=1, le=20)]
    opening: Literal["hinge", "push_latch"]
    height: Millimetres | None = None


class DrawerIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["drawer"]
    count: Annotated[int, Field(ge=1, le=20)]
    height: Millimetres | None = None


class FlapIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["flap"]
    hinged: Literal["bottom", "top"]
    height: Millimetres | None = None


FrontIn = Annotated[DoorIn | DrawerIn | FlapIn, Field(discriminator="type")]


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
    fronts: Annotated[list[FrontIn], Field(max_length=10)] = []
    hardware: Annotated[list[HardwareLineIn], Field(max_length=50)] = []


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


def _boxes_overlap(a: ModuleIn, b: ModuleIn) -> bool:
    """True when two module boxes share volume; touching faces do not count."""
    return (
        a.x < b.x + b.width
        and b.x < a.x + a.width
        and a.y < b.y + b.depth
        and b.y < a.y + a.depth
        and a.z < b.z + b.height
        and b.z < a.z + a.height
    )


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
            if self.envelope is not None and (
                module.x + module.width > self.envelope.width
                or module.z + module.height > self.envelope.height
                or module.y + module.depth > self.envelope.depth
            ):
                raise SpecValidationError(f"{where}: module {module.id!r} lies outside the envelope")
            self._check_fronts(where, module, t)

        for index, part in enumerate(self.extra_parts):
            if part.material not in self.materials:
                raise SpecValidationError(
                    f"extra_parts[{index}].material: undefined material slot {part.material!r}"
                )

        for i, first in enumerate(self.modules):
            for second in self.modules[i + 1 :]:
                if _boxes_overlap(first, second):
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

    def _check_fronts(self, where: str, module: ModuleIn, t: int) -> None:
        document = module.model_dump(mode="json")
        try:
            rects = custom_derive.front_layout(document)
        except custom_derive.DeriveError as error:
            raise SpecValidationError(f"{where}.fronts: {error}") from None
        minimum = custom_derive.MIN_FRONT_MM
        for index, front in enumerate(module.fronts):
            entry = [rect for rect in rects if rect["entry"] == index]
            if any(rect["w"] < minimum or rect["h"] < minimum for rect in entry):
                count = getattr(front, "count", 1)
                raise SpecValidationError(
                    f"{where}.fronts[{index}]: {count} {front.type} front(s) do not fit module "
                    f"{module.id!r} at the minimum front size of {minimum} mm"
                )
            if front.type == "drawer":
                b = self.materials[module.back].thickness_mm if module.back is not None else 0
                if custom_derive.runner_length(module.depth - b) is None:
                    raise SpecValidationError(
                        f"{where}.fronts[{index}]: module {module.id!r} is too shallow for a drawer runner"
                    )
                box_back = module.width - 2 * t - 2 * custom_derive.DRAWER_SIDE_CLEARANCE_MM - 2 * t
                if box_back <= 0:
                    raise SpecValidationError(
                        f"{where}.fronts[{index}]: module {module.id!r} is too narrow for a drawer box"
                    )

    @property
    def context(self) -> CustomBuildContext:
        return CustomBuildContext(overall=custom_derive.overall(self.model_dump(mode="json")))


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
