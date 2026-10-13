"""Turn a restyle request into validated variant plans (the restyle-variants spec).

A plan is plain data the headless render script applies in memory: a piece plan maps
material strings to appearance (slots are resolved here, against the version's own
`spec.json`), a room plan carries one style. Nothing here reads or writes a spec, and
nothing a model says reaches Blender unvalidated: preset ids are looked up, a composed
look or style goes through the same models the configuration uses, and an unknown field
is refused by name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import ValidationError

from app.restyle.presets import APPEARANCE_NOTE, Look, PresetError, Presets, Style

CUSTOM_ID: Final = "custom"
MAX_VARIANTS_PER_REQUEST: Final = 6
ALL: Final = "all"


class RestyleRefused(Exception):
    """A restyle request was refused. `reason` is safe to show the owner."""

    def __init__(self, reason: str, *, field: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.field = field


@dataclass(frozen=True, slots=True)
class VariantPlan:
    """One picture to render: what to apply, and how to record it."""

    base_id: str
    label: str
    kind: str  # "piece" | "room"
    payload: dict[str, Any]  # the JSON the render script reads
    record: dict[str, Any]  # what `scene.json` keeps (preset ids and the slot mapping)

    @property
    def note(self) -> str:
        return APPEARANCE_NOTE


def _problem(error: ValidationError) -> RestyleRefused:
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    name = str(first["loc"][-1]) if first["loc"] else None
    if first["type"] == "extra_forbidden":
        return RestyleRefused(f"{name} is not a field a look or style can carry", field=name)
    return RestyleRefused(f"{where}: {first['msg']}", field=name)


def _look(reference: object, presets: Presets) -> tuple[str, Look]:
    """`(id, look)` of a preset id or a composed look."""
    if isinstance(reference, str):
        try:
            return reference, presets.look(reference)
        except PresetError as error:
            raise RestyleRefused(str(error), field="look") from None
    if isinstance(reference, Mapping):
        try:
            return CUSTOM_ID, Look.model_validate(dict(reference))
        except ValidationError as error:
            raise _problem(error) from None
    raise RestyleRefused("a look is a preset id or a composed look", field="look")


def _style(reference: object, presets: Presets) -> tuple[str, Style]:
    if isinstance(reference, str):
        try:
            return reference, presets.style(reference)
        except PresetError as error:
            raise RestyleRefused(str(error), field="style") from None
    if isinstance(reference, Mapping):
        try:
            return CUSTOM_ID, Style.model_validate(dict(reference))
        except ValidationError as error:
            raise _problem(error) from None
    raise RestyleRefused("a style is a preset id or a composed style", field="style")


def _check_count(count: int) -> None:
    if count == 0:
        raise RestyleRefused("a restyle needs at least one variant", field="variants")
    if count > MAX_VARIANTS_PER_REQUEST:
        raise RestyleRefused(
            f"at most {MAX_VARIANTS_PER_REQUEST} variants per request; ask for fewer", field="variants"
        )


def piece_variants(
    spec: Mapping[str, Any],
    variants: Sequence[Mapping[str, object]],
    presets: Presets,
) -> list[VariantPlan]:
    """Plans for a piece. Each variant maps slot names of `spec` to a look.

    Slots a variant leaves out keep their own appearance, except that slots sharing one
    material string are one Blender material: they must be named together with the same
    look, and are refused by name otherwise.
    """
    _check_count(len(variants))
    slots: Mapping[str, Any] = spec.get("materials") or {}
    plans: list[VariantPlan] = []
    for variant in variants:
        if not variant:
            raise RestyleRefused("a variant names at least one slot", field="slots")
        resolved: dict[str, tuple[str, Look]] = {}
        for slot, reference in variant.items():
            if slot not in slots:
                raise RestyleRefused(
                    f"the piece has no material slot {slot!r}; its slots are {', '.join(slots) or 'none'}",
                    field=slot,
                )
            resolved[slot] = _look(reference, presets)
        by_material: dict[str, dict[str, tuple[str, Look]]] = {}
        for slot, entry in resolved.items():
            by_material.setdefault(slots[slot]["material"], {})[slot] = entry
        for material, named in by_material.items():
            sharing = [s for s, body in slots.items() if body["material"] == material]
            missing = [s for s in sharing if s not in named]
            if missing:
                raise RestyleRefused(
                    f"slots {', '.join(sharing)} share the material {material!r} and change together; "
                    f"name {', '.join(missing)} too",
                    field=missing[0],
                )
            if len({(i, look) for i, look in named.values()}) > 1:
                raise RestyleRefused(
                    f"slots {', '.join(named)} share the material {material!r} and cannot get different looks",
                    field=next(iter(named)),
                )
        materials = {
            slots[slot]["material"]: look.model_dump() for slot, (_, look) in resolved.items()
        }
        ids = sorted({look_id for look_id, _ in resolved.values()})
        plans.append(
            VariantPlan(
                base_id="-".join(ids),
                label=" + ".join(
                    dict.fromkeys(look.label or look_id for look_id, look in resolved.values())
                ),
                kind="piece",
                payload={"mode": "piece", "materials": materials},
                record={
                    "looks": {slot: look_id for slot, (look_id, _) in resolved.items()},
                    "appearance": {slot: look.model_dump() for slot, (_, look) in resolved.items()},
                },
            )
        )
    return plans


def room_variants(styles: Sequence[object], presets: Presets) -> list[VariantPlan]:
    """Plans for a composition: one per style (a preset id, `all`, or a composed style)."""
    references: list[object] = []
    for reference in styles:
        if reference == ALL:
            references.extend(presets.styles)
        else:
            references.append(reference)
    _check_count(len(references))
    plans = []
    for reference in references:
        style_id, style = _style(reference, presets)
        plans.append(
            VariantPlan(
                base_id=style_id,
                label=style.label or style_id,
                kind="room",
                payload={"mode": "room", "style": style.model_dump()},
                record={"style": style_id, "appearance": style.model_dump()},
            )
        )
    return plans


def expand_looks(
    looks: Sequence[object], slots: Sequence[str], presets: Presets
) -> list[dict[str, object]]:
    """The convenience form: each look applied to the same slots, one variant per look
    (`all` is every look)."""
    if not slots:
        raise RestyleRefused("name the slots the looks apply to", field="slots")
    references: list[object] = []
    for reference in looks:
        if reference == ALL:
            references.extend(presets.looks)
        else:
            references.append(reference)
    return [{slot: reference for slot in slots} for reference in references]
