"""Shop data for a `custom_build`, derived by a fixed rule table (custom-build-packages).

Standard-library-only and free of any Blender import, like
`app.blender.spec_contract`: the backend derives a package's cut list,
hardware list and assembly steps here the moment it is created, and the
Phase 3 generator imports this same module inside Blender's own Python so a
generated package's shop data cannot differ from its derived one.

Input is the *normalised* specification — the JSON the service stored after
`app.blender.schemas.CustomBuildSpec` validated it — so nothing here
re-validates. Every figure is a whole millimetre; front sizes round down.

Coordinates: a module's `x`, `y`, `z` are its left, front and bottom faces
(`y` grows away from the viewer, into the wall); `width`, `height` and
`depth` run along x, z and y.

The rule table, per module (`t` the carcass slot's thickness, `b` the back
slot's, or 0 without a back):

- sides: two, full height × (depth − b);
- top and bottom: two, between the sides, (width − 2t) × (depth − b);
- back: one, full width × full height in the back slot, fixed over the rear;
- fixed shelves: between the sides, (width − 2t) × (depth − b);
- fronts, stacked top to bottom in list order over the module's front face
  (an entry without a `height` shares what the others leave), each overlay
  with a 3 mm gap (1.5 mm at every edge):
  - doors split the entry's width; 2, 3 or 4 concealed hinges each for a door
    up to 900 mm, up to 1 600 mm, or taller; a push-latch door also gets one
    latch and no handle note;
  - drawers split the entry's height; each has a front, two sides, a back and a
    bottom, and one runner pair of the longest standard length that fits;
  - a flap covers the entry, with two flap hinges and a pair of stays;
- confirmat screws: 8 per carcass plus 4 per fixed shelf.

Extra parts and free hardware lines are added exactly as given. Part
overrides are applied last: a named row takes the override's quantity, sizes,
material, banding or notes, and its notes record which fields were overridden
and any `[supply: Personal_Supply]` mark pricing reads. A slot the material
review resolved (`resolved_from`) marks every row it produces with a
`[material substituted: …]` note before overrides, so the mark survives them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

GAP_MM: Final = 3
MIN_FRONT_MM: Final = 100
# Drawer box: 13 mm runner clearance each side; box 40 mm lower than its front.
DRAWER_SIDE_CLEARANCE_MM: Final = 13
DRAWER_BOX_HEIGHT_REDUCTION_MM: Final = 40
# Standard runner lengths, and the clearance left behind the longest that fits.
RUNNER_LENGTHS_MM: Final = (250, 300, 350, 400, 450, 500, 550, 600)
RUNNER_REAR_CLEARANCE_MM: Final = 10

HINGE_ID: Final = "hinge-concealed-110"
FLAP_HINGE_ID: Final = "hinge-flap"
FLAP_STAY_ID: Final = "flap-stay"
PUSH_LATCH_ID: Final = "push-latch"
CONFIRMAT_ID: Final = "confirmat-7x50"
EXTRAS_MODULE: Final = "extras"
# The generated model's stable logical layers (furniture-package-generation).
LAYER_NAMES: Final = ("carcass", "backs", "shelves", "fronts", "extras")


class DeriveError(ValueError):
    """A normalised specification the rule table cannot construct."""


def hinges_for_height(height_mm: int) -> int:
    if height_mm <= 900:
        return 2
    if height_mm <= 1600:
        return 3
    return 4


def runner_length(inner_depth_mm: int) -> int | None:
    """The longest standard runner that fits a carcass's inner depth, or None."""
    fitting = [length for length in RUNNER_LENGTHS_MM if length + RUNNER_REAR_CLEARANCE_MM <= inner_depth_mm]
    return fitting[-1] if fitting else None


def overall(spec: Mapping[str, Any]) -> dict[str, int]:
    """The build's overall width, height and depth: its envelope, or its modules' bounds."""
    envelope = spec.get("envelope")
    if envelope is not None:
        return {"w": envelope["width"], "h": envelope["height"], "d": envelope["depth"]}
    modules = spec["modules"]
    if not modules:
        raise DeriveError("a build with no modules needs an envelope")
    x0 = min(m["x"] for m in modules)
    y0 = min(m["y"] for m in modules)
    z0 = min(m["z"] for m in modules)
    return {
        "w": max(m["x"] + m["width"] for m in modules) - x0,
        "h": max(m["z"] + m["height"] for m in modules) - z0,
        "d": max(m["y"] + m["depth"] for m in modules) - y0,
    }


def entry_heights(module: Mapping[str, Any]) -> list[int]:
    """Each front entry's share of the module's height, top to bottom.

    Raises `DeriveError` when the stated heights leave no room for the rest.
    """
    fronts = module["fronts"]
    stated = sum(front["height"] for front in fronts if front.get("height") is not None)
    shared = [front for front in fronts if front.get("height") is None]
    remaining = module["height"] - stated
    if remaining < 0 or (shared and remaining // len(shared) <= 0):
        raise DeriveError("the fronts' stated heights exceed the module's height")
    share = remaining // len(shared) if shared else 0
    return [front["height"] if front.get("height") is not None else share for front in fronts]


def front_layout(module: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every front rectangle of one module, in the module's own front-face frame.

    `x` runs from the module's left face and `z` from its bottom face; each
    entry is one front panel with its size, type and the entry it came from.
    """
    width = module["width"]
    top = module["height"]
    rects: list[dict[str, Any]] = []
    for index, (front, height) in enumerate(zip(module["fronts"], entry_heights(module))):
        bottom = top - height
        kind = front["type"]
        if kind == "door":
            count = front["count"]
            door_w = (width - GAP_MM * count) // count
            for n in range(count):
                rects.append(
                    {
                        "entry": index,
                        "type": "door",
                        "opening": front["opening"],
                        "x": GAP_MM / 2 + n * (door_w + GAP_MM),
                        "z": bottom + GAP_MM / 2,
                        "w": door_w,
                        "h": height - GAP_MM,
                    }
                )
        elif kind == "drawer":
            count = front["count"]
            drawer_h = (height - GAP_MM * count) // count
            for n in range(count):
                rects.append(
                    {
                        "entry": index,
                        "type": "drawer",
                        "x": GAP_MM / 2,
                        "z": top - GAP_MM / 2 - (n + 1) * drawer_h - n * GAP_MM,
                        "w": width - GAP_MM,
                        "h": drawer_h,
                    }
                )
        else:  # flap
            rects.append(
                {
                    "entry": index,
                    "type": "flap",
                    "hinged": front["hinged"],
                    "x": GAP_MM / 2,
                    "z": bottom + GAP_MM / 2,
                    "w": width - GAP_MM,
                    "h": height - GAP_MM,
                }
            )
        top = bottom
    return rects


def _part(
    identifier: str,
    name: str,
    *,
    qty: int,
    l: int,
    w: int,
    t: int,
    material: str,
    grain: str,
    banding: str,
    notes: str,
    module: str,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "qty": qty,
        "l": l,
        "w": w,
        "t": t,
        "material": material,
        "grain": grain,
        "banding": banding,
        "notes": notes,
        "module": module,
    }


class _Hardware:
    """Hardware lines merged by id, in the order each id first appears."""

    def __init__(self) -> None:
        self.lines: dict[str, dict[str, Any]] = {}

    def add(self, identifier: str, item: str, qty: int, notes: str = "") -> None:
        existing = self.lines.get(identifier)
        if existing is None:
            self.lines[identifier] = {"id": identifier, "item": item, "qty": qty, "notes": notes}
        else:
            existing["qty"] += qty

    def free(self, lines: list[Mapping[str, Any]]) -> None:
        for line in lines:
            self.add(line["id"], line["item"], line["qty"], line.get("notes") or "")


def _module_rows(
    module: Mapping[str, Any], materials: Mapping[str, Mapping[str, Any]], hardware: _Hardware
) -> list[dict[str, Any]]:
    mid = module["id"]
    carcass = materials[module["carcass"]]
    t, material = carcass["thickness_mm"], carcass["material"]
    back = materials[module["back"]] if module.get("back") is not None else None
    b = back["thickness_mm"] if back is not None else 0
    width, height, depth = module["width"], module["height"], module["depth"]
    inner_w, inner_d = width - 2 * t, depth - b

    rows = [
        _part(
            f"{mid}-side", "Side", qty=2, l=height, w=inner_d, t=t, material=material,
            grain="length (vertical)", banding="front edge",
            notes="Rule: sides full height × depth less the back", module=mid,
        ),
        _part(
            f"{mid}-top-bottom", "Top/bottom", qty=2, l=inner_w, w=inner_d, t=t, material=material,
            grain="length (left-right)", banding="front edge",
            notes="Rule: top and bottom between the sides", module=mid,
        ),
    ]
    if back is not None:
        rows.append(
            _part(
                f"{mid}-back", "Back", qty=1, l=height, w=width, t=b, material=back["material"],
                grain="length (vertical)", banding="none",
                notes="Rule: full-size back fixed over the carcass rear", module=mid,
            )
        )
    shelves = module["shelves"]
    if shelves:
        rows.append(
            _part(
                f"{mid}-shelf", "Fixed shelf", qty=shelves, l=inner_w, w=inner_d, t=t,
                material=material, grain="length (left-right)", banding="front edge",
                notes="Rule: fixed shelves between the sides at the back-reduced depth", module=mid,
            )
        )
    hardware.add(
        CONFIRMAT_ID,
        "Confirmat screw 7×50 mm",
        8 + 4 * shelves,
        "Rule: 8 per carcass plus 4 per fixed shelf",
    )

    rects = front_layout(module)
    bottom_slot = back if back is not None else carcass
    for index, front in enumerate(module["fronts"]):
        entry = [rect for rect in rects if rect["entry"] == index]
        count = len(entry)
        first = entry[0]
        prefix = f"{mid}-{front['type']}-{index + 1}"
        if front["type"] == "door":
            push = front["opening"] == "push_latch"
            rows.append(
                _part(
                    prefix, "Door", qty=count, l=first["h"], w=first["w"], t=t, material=material,
                    grain="length (vertical)", banding="all edges",
                    notes=(
                        "Rule: overlay door, 3 mm gap; push-latch, no handle"
                        if push
                        else "Rule: overlay door, 3 mm gap; handle as specified"
                    ),
                    module=mid,
                )
            )
            hardware.add(
                HINGE_ID,
                "Concealed hinge 110°",
                hinges_for_height(first["h"]) * count,
                "Rule: 2/3/4 per door up to 900/1600 mm tall/above",
            )
            if push:
                hardware.add(PUSH_LATCH_ID, "Push latch", count, "Rule: one per push-latch door")
        elif front["type"] == "drawer":
            runner = runner_length(inner_d)
            if runner is None:
                raise DeriveError(f"module {mid!r} is too shallow for a drawer runner")
            box_w = inner_w - 2 * DRAWER_SIDE_CLEARANCE_MM
            box_h = first["h"] - DRAWER_BOX_HEIGHT_REDUCTION_MM
            rows.extend(
                [
                    _part(
                        f"{prefix}-front", "Drawer front", qty=count, l=first["w"], w=first["h"], t=t,
                        material=material, grain="length (left-right)", banding="all edges",
                        notes="Rule: overlay drawer front, 3 mm gap", module=mid,
                    ),
                    _part(
                        f"{prefix}-side", "Drawer side", qty=2 * count, l=runner, w=box_h, t=t,
                        material=material, grain="length (front-back)", banding="top edge",
                        notes=f"Rule: runner length × front height less {DRAWER_BOX_HEIGHT_REDUCTION_MM} mm",
                        module=mid,
                    ),
                    _part(
                        f"{prefix}-back", "Drawer back", qty=count, l=box_w - 2 * t, w=box_h, t=t,
                        material=material, grain="length (left-right)", banding="top edge",
                        notes="Rule: between the drawer sides", module=mid,
                    ),
                    _part(
                        f"{prefix}-bottom", "Drawer bottom", qty=count, l=runner, w=box_w,
                        t=bottom_slot["thickness_mm"], material=bottom_slot["material"],
                        grain="none", banding="none",
                        notes="Rule: full box width × runner length, fixed under the sides", module=mid,
                    ),
                ]
            )
            hardware.add(
                f"drawer-runner-{runner}",
                f"Drawer runner pair, {runner} mm",
                count,
                "Rule: one pair per drawer, longest standard length that fits",
            )
        else:  # flap
            rows.append(
                _part(
                    prefix, "Flap", qty=1, l=first["w"], w=first["h"], t=t, material=material,
                    grain="length (left-right)", banding="all edges",
                    notes=f"Rule: {front['hinged']}-hinged overlay flap, 3 mm gap", module=mid,
                )
            )
            hardware.add(FLAP_HINGE_ID, "Flap hinge", 2, "Rule: two per flap")
            hardware.add(FLAP_STAY_ID, "Flap stay", 2, "Rule: one pair per flap")

    hardware.free(module.get("hardware") or [])
    return rows


def _assembly(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    bodies: list[tuple[str, str]] = [
        (
            "Cut and edge-band",
            "Cut and label every part on the cut list. Edge-band the edges each row names before assembly.",
        )
    ]
    for module in spec["modules"]:
        body = f"Fix the top and bottom between the sides of {module['id']} with confirmats and glue"
        if module["shelves"]:
            body += f", then the {module['shelves']} fixed shelves"
        body += "."
        if module.get("back") is not None:
            body += " Square the carcass and fix the back over its rear."
        bodies.append((f"Carcass: {module['name']}", body))
    for module in spec["modules"]:
        if not module["fronts"]:
            continue
        kinds = ", ".join(
            f"{front.get('count', 1)} {front['type']}{'s' if front.get('count', 1) > 1 else ''}"
            for front in module["fronts"]
        )
        bodies.append(
            (
                f"Fronts: {module['name']}",
                f"Fit the hardware and hang {kinds} on {module['id']}; set every gap to 3 mm.",
            )
        )
    if spec.get("extra_parts"):
        names = ", ".join(part["id"] for part in spec["extra_parts"])
        bodies.append(("Extra parts", f"Fit the extra parts as specified: {names}."))
    for note in spec.get("assembly_notes") or []:
        bodies.append(("Workshop note", note))
    bodies.append(("Install", "Position, level and fix the build in place."))
    return [{"step": index + 1, "title": title, "body": body} for index, (title, body) in enumerate(bodies)]


def _rule_rows(spec: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(cut-list rows, hardware rows) from the rule table and the extras, before overrides."""
    materials = spec["materials"]
    hardware = _Hardware()
    parts: list[dict[str, Any]] = []
    for module in spec["modules"]:
        parts.extend(_module_rows(module, materials, hardware))
    for extra in spec.get("extra_parts") or []:
        slot = materials[extra["material"]]
        notes = extra.get("notes") or "Extra part as specified"
        if extra.get("supply") is not None:
            notes += f" {supply_note(extra['supply'])}"
        parts.append(
            _part(
                extra["id"], extra["name"], qty=extra["qty"], l=extra["length"], w=extra["width"],
                t=slot["thickness_mm"], material=slot["material"],
                grain="length" if extra["grain"] == "length" else "none", banding="none",
                notes=notes, module=EXTRAS_MODULE,
            )
        )
        hardware.free(extra.get("hardware") or [])
    hardware.free(spec.get("hardware") or [])
    _mark_substitutions(parts, materials)
    return parts, list(hardware.lines.values())


_LANE_WORDING: Final = {
    "auto": "pre-approved by rule",
    "recommended": "recommended by rule",
    "chosen": "chosen",
}


def substitution_note(slot: Mapping[str, Any]) -> str:
    """The mark a row of a slot resolved by the material review carries."""
    origin = slot["resolved_from"]
    original = origin["material"]
    if origin["thickness_mm"] != slot["thickness_mm"]:
        original = f"{original} ({origin['thickness_mm']} mm)"
    return (
        f"material substituted: {original} → {slot['material']}; "
        f"{_LANE_WORDING[origin['lane']]}, accepted by {origin['accepted_by']} on {origin['accepted_at']}"
    )


def _mark_substitutions(parts: list[dict[str, Any]], materials: Mapping[str, Any]) -> None:
    """Append the substitution note to every row a resolved slot produced (before overrides)."""
    for slot in materials.values():
        if not slot.get("resolved_from"):
            continue
        note = substitution_note(slot)
        for part in parts:
            if part["material"] == slot["material"] and part["t"] == slot["thickness_mm"]:
                part["notes"] = f"{part['notes']} [{note}]"


def base_parts(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The cut-list rows before any part override: what an override may name."""
    return _rule_rows(spec)[0]


def supply_note(supply: str) -> str:
    """The marker pricing reads to resolve a part to its supply entry."""
    return f"[supply: {supply}]"


# An override field and the cut-list column it replaces.
_OVERRIDE_COLUMNS: Final = (
    ("qty", "qty"),
    ("length", "l"),
    ("width", "w"),
    ("thickness", "t"),
    ("material", "material"),
    ("banding", "banding"),
    ("notes", "notes"),
)


def _apply_overrides(parts: list[dict[str, Any]], overrides: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Each named row takes the override's values; its id, module and position stay."""
    by_id = {override["id"]: override for override in overrides}
    unknown = set(by_id) - {part["id"] for part in parts}
    if unknown:
        raise DeriveError(f"no derived cut-list row is named {min(unknown)!r}")
    result: list[dict[str, Any]] = []
    for part in parts:
        override = by_id.get(part["id"])
        if override is None:
            result.append(part)
            continue
        row = dict(part)
        changed = []
        for field, column in _OVERRIDE_COLUMNS:
            if override.get(field) is not None:
                row[column] = override[field]
                changed.append(field)
        if changed:
            row["notes"] = f"{row['notes']} [overridden: {', '.join(changed)}]"
        if override.get("supply") is not None:
            row["notes"] = f"{row['notes']} {supply_note(override['supply'])}"
        result.append(row)
    return result


def derive(spec: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(cut-list rows, hardware rows, assembly steps) for a normalised spec.

    Rows follow module order, then rule order within a module, then extra
    parts; hardware follows the order each id first appears. Part overrides
    are applied last. The same input always yields identical output.
    """
    parts, hardware = _rule_rows(spec)
    parts = _apply_overrides(parts, spec.get("part_overrides") or [])
    return parts, hardware, _assembly(spec)


def emitted_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """The `spec.json` a derived package publishes: the studio's one source.

    `modules` holds each module's box as numbers only (the studio's existing
    type), `fronts` every front rectangle in build coordinates, and `input`
    the normalised specification itself. `layers` is empty: a derived package
    has no model until the Phase 3 generator replaces this document.
    """
    parts, hardware, assembly = derive(spec)
    fronts: list[dict[str, Any]] = []
    for module in spec["modules"]:
        for rect in front_layout(module):
            fronts.append(
                {**rect, "module": module["id"], "x": module["x"] + rect["x"], "z": module["z"] + rect["z"]}
            )
    return {
        "name": spec["name"],
        "kind": spec["kind"],
        "schema_version": spec["schema_version"],
        "units": spec["units"],
        "template": spec.get("template"),
        "overall": overall(spec),
        "modules": {
            module["id"]: {
                "x": module["x"],
                "y": module["y"],
                "z": module["z"],
                "w": module["width"],
                "h": module["height"],
                "d": module["depth"],
                "shelves": module["shelves"],
            }
            for module in spec["modules"]
        },
        "module_names": {module["id"]: module["name"] for module in spec["modules"]},
        "fronts": fronts,
        "parts": parts,
        "hardware": hardware,
        "assembly": assembly,
        "layers": {},
        "input": dict(spec),
        "notes": [
            "All dimensions millimetres.",
            "Derived from a validated custom-build specification by a fixed rule table.",
        ],
    }
