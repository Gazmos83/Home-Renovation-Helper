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
- shelf heights: evenly spaced, fixed shelves lowest; or, when stated, each
  underside at `shelf_positions_mm`, or one `shelf_spacing_mm` clear gap above
  the board below, measured from the top face of the bottom panel;
- dividers: `dividers` full-height boards between the top and bottom,
  (height − 2t) × (depth − b), splitting the inner width into bays (evenly,
  rounded down, or at `divider_positions_mm` from the left side's inner face);
  shelves then sit in every bay at the same heights, cut to the bay's width,
  one row while the bays share a width, else one `-bay-<n>` row per bay;
- fronts, stacked top to bottom in list order over the module's front face
  (an entry without a `height` shares what the others leave), each overlay
  with a 3 mm gap (1.5 mm at every edge):
  - doors split the entry's width; 2, 3 or 4 concealed hinges each for a door
    up to 900 mm, up to 1 600 mm, or taller; a push-latch door also gets one
    latch and no handle note;
  - drawers split the entry's height; each has a front, two sides, a back and a
    bottom, and one runner pair of the longest standard length that fits;
  - a flap covers the entry, with two flap hinges and a pair of stays;
- adjustable shelves: one row between the sides at the back-reduced depth, less
  `ADJUSTABLE_SHELF_CLEARANCE_MM` (rounded down to a whole millimetre); pins
  per shelf times shelves of the module's shelf-pin item, or no quantity when
  its data sheet lacks the value;
- hinges are keyed by the door's hinge item; the count per door is the item's
  own count table when its data sheet has one, else the height rule above; a
  data sheet that names a mounting-plate item adds one plate per hinge;
- confirmat screws: 8 per carcass plus 4 per fixed shelf board plus 4 per divider;
- wall shelves (outside any module): one board row each, and one bracket line
  per bracket item: the owner's positions, else the count the bracket rules give.

Hardware inputs (`hardware_inputs.json`: `data_sheets` by hardware key, each
`{kind, maker, model, values, source, updated_at}`, and `rules` by check name,
each `{rule_id, params, source}`) are optional. Without them (`inputs=None`) the
rows and hardware come out as they always did and there is no drilling list.
With them, `drilling(spec, inputs)` runs the closed `CALCULATIONS` registry:
every position is an exact value, a range or a rule in words, and a value that
is missing is named in a warning, never guessed.

Extra parts and free hardware lines are added exactly as given. Part
overrides are applied last: a named row takes the override's quantity, sizes,
material, banding or notes, and its notes record which fields were overridden
and any `[supply: Personal_Supply]` mark pricing reads. A slot the material
review resolved (`resolved_from`) marks every row it produces with a
`[material substituted: …]` note before overrides, so the mark survives them.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any, Final, NamedTuple

GAP_MM: Final = 3
# The width an adjustable shelf is cut short of the gap between the sides.
ADJUSTABLE_SHELF_CLEARANCE_MM: Final = 1.5
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
SHELF_PIN_ID: Final = "shelf-pin"
BRACKET_COUNT_CHECK: Final = "shelf_bracket_count_for_length"
BRACKET_SPACING_CHECK: Final = "shelf_bracket_spacing_mm"
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


def shelf_centres(module: Mapping[str, Any], t: int) -> list[float]:
    """Each shelf's centre above the module's bottom face, lowest first: fixed shelves, then adjustable.

    A stated `shelf_positions_mm` gives each shelf's underside above the top face of the
    bottom panel; a stated `shelf_spacing_mm` is the clear gap below each shelf; without
    either, the shelves are spaced evenly between the bottom and top panels.
    """
    count = module["shelves"] + module.get("adjustable_shelves", 0)
    positions = module.get("shelf_positions_mm")
    spacing = module.get("shelf_spacing_mm")
    if positions:
        undersides = list(positions)
    elif spacing:
        undersides = [spacing + k * (spacing + t) for k in range(count)]
    else:
        step = (module["height"] - 2 * t) / (count + 1)
        return [t + step * (k + 1) for k in range(count)]
    return [t + underside + t / 2 for underside in undersides]


def shelf_undersides(module: Mapping[str, Any], t: int) -> list[float]:
    """Each shelf's underside above the top face of the bottom panel, lowest first."""
    return [centre - t - t / 2 for centre in shelf_centres(module, t)]


def bays(module: Mapping[str, Any], t: int) -> list[tuple[int, int]]:
    """Each bay's left edge and width, from the inner face of the left side, left to right.

    A stated `divider_positions_mm` gives each divider's left face; without it the
    dividers split the inner width evenly, each bay rounded down and the remainder
    left to the last bay.
    """
    inner_w = module["width"] - 2 * t
    count = module.get("dividers", 0)
    if not count:
        return [(0, inner_w)]
    positions = module.get("divider_positions_mm")
    if positions:
        lefts = [0, *(position + t for position in positions)]
        rights = [*positions, inner_w]
        return [(left, right - left) for left, right in zip(lefts, rights)]
    width = (inner_w - count * t) // (count + 1)
    found = [(k * (width + t), width) for k in range(count)]
    last = count * (width + t)
    return [*found, (last, inner_w - last)]


def bay_cut_widths(module: Mapping[str, Any], t: int) -> list[int]:
    """Each bay's width as the cut list states it: evenly split bays share the rounded-down width."""
    found = bays(module, t)
    if module.get("dividers", 0) and not module.get("divider_positions_mm"):
        return [found[0][1]] * len(found)
    return [width for _, width in found]


def overall(spec: Mapping[str, Any]) -> dict[str, int]:
    """The build's overall width, height and depth: its envelope, or its modules' bounds."""
    envelope = spec.get("envelope")
    if envelope is not None:
        return {"w": envelope["width"], "h": envelope["height"], "d": envelope["depth"]}
    boxes = [(m["x"], m["y"], m["z"], m["width"], m["depth"], m["height"]) for m in spec["modules"]]
    for shelf in spec.get("wall_shelves") or []:
        thickness = spec["materials"][shelf["material"]]["thickness_mm"]
        boxes.append((shelf["x"], shelf["y"], shelf["z"], shelf["length"], shelf["depth"], thickness))
    if not boxes:
        raise DeriveError("a build with no modules needs an envelope")
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    z0 = min(b[2] for b in boxes)
    return {
        "w": max(b[0] + b[3] for b in boxes) - x0,
        "h": max(b[2] + b[5] for b in boxes) - z0,
        "d": max(b[1] + b[4] for b in boxes) - y0,
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

    def add(self, identifier: str, item: str, qty: int | str, notes: str = "") -> None:
        """`qty` is `""` when a missing value leaves the quantity unknown; an unknown stays unknown."""
        existing = self.lines.get(identifier)
        if existing is None:
            self.lines[identifier] = {"id": identifier, "item": item, "qty": qty, "notes": notes}
        elif existing["qty"] == "" or qty == "":
            existing["qty"] = ""
            if notes and notes not in existing["notes"]:
                existing["notes"] = f"{existing['notes']}; {notes}" if existing["notes"] else notes
        else:
            existing["qty"] += qty

    def free(self, lines: list[Mapping[str, Any]]) -> None:
        for line in lines:
            self.add(line["id"], line["item"], line["qty"], line.get("notes") or "")


def bay_rows(prefix: str, name: str, per_bay: int, widths: list[int]) -> list[tuple[str, str, int, int]]:
    """One row for bays of one width, else one row per bay named `-bay-<n>` from the left."""
    if len(set(widths)) == 1:
        return [(prefix, name, per_bay * len(widths), widths[0])]
    return [(f"{prefix}-bay-{n}", f"{name}, bay {n}", per_bay, width) for n, width in enumerate(widths, start=1)]


def _module_rows(
    module: Mapping[str, Any],
    materials: Mapping[str, Mapping[str, Any]],
    hardware: _Hardware,
    inputs: Mapping[str, Any] | None = None,
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
    dividers = module.get("dividers", 0)
    if dividers:
        rows.append(
            _part(
                f"{mid}-divider", "Divider", qty=dividers, l=height - 2 * t, w=inner_d, t=t, material=material,
                grain="length (vertical)", banding="front edge",
                notes="Rule: full-height dividers between the top and bottom at the back-reduced depth", module=mid,
            )
        )
    widths = bay_cut_widths(module, t)
    shelves = module["shelves"]
    if shelves and not dividers:
        rows.append(
            _part(
                f"{mid}-shelf", "Fixed shelf", qty=shelves, l=inner_w, w=inner_d, t=t,
                material=material, grain="length (left-right)", banding="front edge",
                notes="Rule: fixed shelves between the sides at the back-reduced depth", module=mid,
            )
        )
    elif shelves:
        for row_id, name, qty, width in bay_rows(f"{mid}-shelf", "Fixed shelf", shelves, widths):
            rows.append(
                _part(
                    row_id, name, qty=qty, l=width, w=inner_d, t=t,
                    material=material, grain="length (left-right)", banding="front edge",
                    notes="Rule: fixed shelves in every bay between the sides and dividers at the back-reduced depth",
                    module=mid,
                )
            )
    adjustable = module.get("adjustable_shelves", 0)
    if adjustable and not dividers:
        rows.append(
            _part(
                f"{mid}-adjustable-shelf", "Adjustable shelf", qty=adjustable,
                l=math.floor(inner_w - ADJUSTABLE_SHELF_CLEARANCE_MM), w=inner_d, t=t,
                material=material, grain="length (left-right)", banding="front edge",
                notes=(
                    f"Rule: between the sides less {ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance "
                    "(rounded down), at the back-reduced depth"
                ),
                module=mid,
            )
        )
    elif adjustable:
        for row_id, name, qty, width in bay_rows(f"{mid}-adjustable-shelf", "Adjustable shelf", adjustable, widths):
            rows.append(
                _part(
                    row_id, name, qty=qty, l=math.floor(width - ADJUSTABLE_SHELF_CLEARANCE_MM), w=inner_d, t=t,
                    material=material, grain="length (left-right)", banding="front edge",
                    notes=(
                        f"Rule: in every bay less {ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance "
                        "(rounded down), at the back-reduced depth"
                    ),
                    module=mid,
                )
            )
    if adjustable:
        _pin_line(module, adjustable * len(widths), inputs, hardware)
    if dividers:
        hardware.add(
            CONFIRMAT_ID,
            "Confirmat screw 7×50 mm",
            8 + 4 * shelves * len(widths) + 4 * dividers,
            "Rule: 8 per carcass plus 4 per fixed shelf board plus 4 per divider",
        )
    else:
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
            _hinge_lines(front, first["h"], count, inputs, hardware)
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


# --- hardware inputs: data sheets and bracket rules --------------------------------------
#
# A measured value in a data sheet or a rule is `{"value": n}` or `{"min": a, "max": b}`; it is turned
# into a *form* (`{"mm": n}` / `{"min_mm": a, "max_mm": b}`) and kept as given. A form is also what a
# drilling position is, besides `{"rule": "<words>"}`. Nothing here picks a value inside a range.

EVEN_RULE: Final = "evenly spaced between them"
Form = dict[str, Any]


def _sheet(inputs: Mapping[str, Any] | None, key: str) -> Mapping[str, Any] | None:
    return ((inputs or {}).get("data_sheets") or {}).get(key)


def _rule(inputs: Mapping[str, Any] | None, check: str) -> Mapping[str, Any] | None:
    return ((inputs or {}).get("rules") or {}).get(check)


def _form(raw: Mapping[str, Any] | None) -> Form | None:
    if not raw:
        return None
    if "value" in raw:
        return {"mm": raw["value"]}
    if "min" in raw and "max" in raw:
        return {"min_mm": raw["min"], "max_mm": raw["max"]}
    return None


def _n(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _num(value: float) -> float | int:
    rounded = round(value, 1)
    return int(rounded) if rounded == int(rounded) else rounded


def _say(form: Form) -> str:
    if "mm" in form:
        return f"{_n(form['mm'])} mm"
    if "min_mm" in form:
        return f"{_n(form['min_mm'])}–{_n(form['max_mm'])} mm"
    if "count" in form:
        return str(form["count"])
    return str(form["rule"])


def _shift(form: Form, by: float) -> Form:
    if "mm" in form:
        return {"mm": _num(form["mm"] + by)}
    return {"min_mm": _num(form["min_mm"] + by), "max_mm": _num(form["max_mm"] + by)}


def _shortest(form: Form) -> float:
    return form["mm"] if "mm" in form else form["min_mm"]


def _hinge_count(sheet: Mapping[str, Any] | None, height_mm: int) -> tuple[int, bool]:
    """(hinges per door, whether the item's own count table decided it)."""
    table = ((sheet or {}).get("values") or {}).get("count_table")
    if not table:
        return hinges_for_height(height_mm), False
    for row in sorted(table, key=lambda r: r["max_height_mm"]):
        if height_mm <= row["max_height_mm"]:
            return row["hinges"], True
    return max(table, key=lambda r: r["max_height_mm"])["hinges"], True


def _hinge_lines(
    front: Mapping[str, Any], door_height: int, doors: int, inputs: Mapping[str, Any] | None, hardware: _Hardware
) -> None:
    key = front.get("hinge") or HINGE_ID
    sheet = _sheet(inputs, key)
    per_door, from_table = _hinge_count(sheet, door_height)
    if sheet is not None:
        item = f"{sheet['maker']} {sheet['model']}"
    elif key == HINGE_ID:
        item = "Concealed hinge 110°"
    else:
        item = f"Hinge {key}"
    note = (
        "Rule: per the item's data sheet count table"
        if from_table
        else "Rule: 2/3/4 per door up to 900/1600 mm tall/above"
    )
    hardware.add(key, item, per_door * doors, note)
    plate = ((sheet or {}).get("values") or {}).get("plate_item")
    if plate:
        hardware.add(plate, f"Mounting plate for {key}", per_door * doors, "Rule: one plate per hinge")


def _pin_line(module: Mapping[str, Any], shelves: int, inputs: Mapping[str, Any] | None, hardware: _Hardware) -> None:
    key = module.get("shelf_pin") or SHELF_PIN_ID
    sheet = _sheet(inputs, key)
    per_shelf = ((sheet or {}).get("values") or {}).get("pins_per_shelf")
    if per_shelf is None:
        reason = "no data sheet" if sheet is None else "pins per shelf missing from its data sheet"
        hardware.add(key, f"Shelf pin {key}", "", f"No quantity: {reason}")
    else:
        hardware.add(key, f"{sheet['maker']} {sheet['model']}", per_shelf * shelves, "Rule: pins per shelf × adjustable shelves")


def bracket_plan(shelf: Mapping[str, Any], inputs: Mapping[str, Any] | None) -> dict[str, Any]:
    """The bracket count of one wall shelf and why it may be unknown.

    `owner` is true when the owner's positions decide. Otherwise the count comes from the count rule and
    needs the spacing rule's end distance too; `missing` names a rule that is not in the inputs and
    `problem` says when the board is too short for it. `count` is None when either is set.
    """
    owner = shelf.get("bracket_positions_mm")
    if owner:
        return {"owner": True, "count": len(owner), "missing": [], "problem": None, "end": None, "source": None}
    count_rule = _rule(inputs, BRACKET_COUNT_CHECK)
    spacing_rule = _rule(inputs, BRACKET_SPACING_CHECK)
    missing = []
    if count_rule is None:
        missing.append("bracket count rule")
    end = _form((spacing_rule or {}).get("params", {}).get("end_distance_mm"))
    if end is None:
        missing.append("bracket end distance")
    plan: dict[str, Any] = {
        "owner": False, "count": None, "missing": missing, "problem": None, "end": end,
        "source": (spacing_rule or count_rule or {}).get("source"),
    }
    if missing:
        return plan
    if 2 * _shortest(end) >= shelf["length"]:
        plan["problem"] = "board too short for the bracket end distance"
        return plan
    table = sorted(count_rule["params"]["table"], key=lambda r: r["max_length_mm"])
    row = next((r for r in table if shelf["length"] <= r["max_length_mm"]), table[-1])
    plan["count"] = row["min_brackets"]
    return plan


def _wall_shelf_rows(
    spec: Mapping[str, Any], hardware: _Hardware, inputs: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    rows = []
    materials = spec["materials"]
    for shelf in spec.get("wall_shelves") or []:
        slot = materials[shelf["material"]]
        rows.append(
            _part(
                shelf["id"], shelf["name"], qty=1, l=shelf["length"], w=shelf["depth"], t=slot["thickness_mm"],
                material=slot["material"], grain="length (left-right)", banding="front edge",
                notes="Rule: wall-hung board on brackets", module=shelf["id"],
            )
        )
        plan = bracket_plan(shelf, inputs)
        if plan["count"] is not None:
            hardware.add(
                shelf["bracket"], f"Shelf bracket {shelf['bracket']}", plan["count"],
                "Rule: the owner's bracket positions" if plan["owner"] else "Rule: bracket count rule for the board's length",
            )
        else:
            reason = plan["problem"] or f"missing: {', '.join(plan['missing'])}"
            hardware.add(shelf["bracket"], f"Shelf bracket {shelf['bracket']}", "", f"No quantity: {reason}")
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
        if module.get("dividers"):
            body += f", then the {module['dividers']} dividers between them"
        if module["shelves"]:
            body += f", then the {module['shelves']} fixed shelves"
        body += "."
        if module.get("adjustable_shelves"):
            body += f" Fit the {module['adjustable_shelves']} adjustable shelves on shelf pins in the drilled holes."
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
    if spec.get("wall_shelves"):
        names = ", ".join(shelf["id"] for shelf in spec["wall_shelves"])
        bodies.append(
            ("Wall shelves", f"Mark the bracket positions from the drilling list, fix the brackets and hang: {names}.")
        )
    if spec.get("extra_parts"):
        names = ", ".join(part["id"] for part in spec["extra_parts"])
        bodies.append(("Extra parts", f"Fit the extra parts as specified: {names}."))
    for note in spec.get("assembly_notes") or []:
        bodies.append(("Workshop note", note))
    bodies.append(("Install", "Position, level and fix the build in place."))
    return [{"step": index + 1, "title": title, "body": body} for index, (title, body) in enumerate(bodies)]


def _rule_rows(
    spec: Mapping[str, Any], inputs: Mapping[str, Any] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(cut-list rows, hardware rows) from the rule table and the extras, before overrides."""
    materials = spec["materials"]
    hardware = _Hardware()
    parts: list[dict[str, Any]] = []
    for module in spec["modules"]:
        parts.extend(_module_rows(module, materials, hardware, inputs))
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
    parts.extend(_wall_shelf_rows(spec, hardware, inputs))
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


def base_parts(spec: Mapping[str, Any], inputs: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """The cut-list rows before any part override: what an override may name."""
    return _rule_rows(spec, inputs)[0]


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


# --- drilling: a closed registry of cited calculations ------------------------------------
#
# Each calculation is a pure function of (spec, inputs) returning `DrillEntry` dicts:
#   calculation, part, what, text, positions [{label, position: form, from}],
#   values [{name, form | None, source}], missing [value names], problem (str | None), counts.
# A calculation never reads another's output. To add one: append a `Calculation`, give its data-sheet
# kind in `app.guidelines.datasheets`, and add its tests; nothing below changes.

DrillEntry = dict[str, Any]


class Calculation(NamedTuple):
    name: str
    kind: str  # the data-sheet kind or rule it reads
    inputs: tuple[str, ...]
    run: Callable[[Mapping[str, Any], Mapping[str, Any]], list[DrillEntry]]


def _entry(
    calculation: str, part: str, what: str, *, positions: list[dict[str, Any]], values: list[dict[str, Any]],
    missing: list[str], problem: str | None = None, counts: Mapping[str, int | None] | None = None,
    clauses: list[str], source_name: str,
) -> DrillEntry:
    text = f"{part}: " + "; ".join(clauses) if clauses else f"{part}: {what}"
    if missing:
        text += f"; blank, missing: {', '.join(missing)}"
    if problem:
        text += f"; blank, {problem}"
    return {
        "calculation": calculation, "part": part, "what": what, "text": f"{text} ({source_name})",
        "positions": positions, "values": values, "missing": missing, "problem": problem,
        "counts": dict(counts or {}),
    }


def _value(values: Mapping[str, Any], field: str, name: str, source: str, missing: list[str]) -> dict[str, Any]:
    raw = values.get(field)
    if raw is None:
        missing.append(name)
        return {"name": name, "form": None, "source": source}
    form = {"count": raw} if isinstance(raw, int) and not isinstance(raw, bool) else _form(raw)
    return {"name": name, "form": form, "source": source}


def _no_sheet(key: str) -> list[str]:
    return [f"no data sheet for {key}"]


def _along(length: float, n: int, end: Form, origins: tuple[str, str]) -> list[dict[str, Any]]:
    """`n` positions along `length`: the outer two at `end` from each end, the rest evenly between.

    Exact values give exact positions from the first origin. A ranged end gives the outer two as that
    range from their own end, and the others as a rule in words: no number is picked inside the range.
    """
    first, last = origins
    if n == 1:
        return [{"label": "1", "position": end, "from": first}]
    if "mm" in end:
        gap = (length - 2 * end["mm"]) / (n - 1)
        return [{"label": str(i + 1), "position": {"mm": _num(end["mm"] + i * gap)}, "from": first} for i in range(n)]
    positions = [{"label": "1", "position": end, "from": first}]
    positions += [{"label": str(i + 1), "position": {"rule": EVEN_RULE}, "from": first} for i in range(1, n - 1)]
    positions.append({"label": str(n), "position": end, "from": last})
    return positions


def _along_text(noun: str, positions: list[dict[str, Any]], origins: tuple[str, str]) -> str:
    if all("rule" not in p["position"] for p in positions):
        if len({p["from"] for p in positions}) == 1 and "mm" in positions[0]["position"]:
            heights = ", ".join(_n(p["position"]["mm"]) for p in positions)
            return f"{noun}s at {heights} mm from the {origins[0]}"
        outer = _say(positions[0]["position"])
        return f"{noun}s {positions[0]['label']} and {positions[-1]['label']} at {outer} from each end"
    outer = positions[0]
    inner = [p["label"] for p in positions if "rule" in p["position"]]
    clause = f"{noun}s {outer['label']} and {positions[-1]['label']} at {_say(outer['position'])} from each end"
    if inner:
        clause += f"; {noun} {', '.join(inner)} {EVEN_RULE}"
    return clause


def _warning(entry: DrillEntry) -> list[str]:
    out = []
    where = f"({entry['part']}, {entry['what']})"
    if entry["missing"]:
        out.append(f"drilling positions missing: {', '.join(entry['missing'])} {where}")
    if entry["problem"]:
        out.append(f"{entry['problem']} {where}")
    return out


# Shelf pins.

_PIN_FIELDS: Final = (
    ("hole_diameter_mm", "hole diameter"), ("hole_depth_mm", "hole depth"), ("pitch_mm", "pitch"),
    ("first_hole_mm", "first hole"), ("last_hole_mm", "last hole"), ("front_setback_mm", "front setback"),
    ("rear_setback_mm", "rear setback"), ("pins_per_shelf", "pins per shelf"),
)


def _shelf_pin_entries(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[DrillEntry]:
    entries = []
    for module in spec["modules"]:
        if not module.get("adjustable_shelves"):
            continue
        key = module.get("shelf_pin") or SHELF_PIN_ID
        part, what = f"{module['id']}-side", "shelf-pin holes"
        sheet = _sheet(inputs, key)
        dividers = module.get("dividers", 0)
        divider_part = f"{module['id']}-divider"
        if sheet is None:
            entries.append(_entry(
                "shelf_pins", part, what, positions=[], values=[], missing=_no_sheet(key),
                counts={"shelf_pin_holes": None}, clauses=[], source_name=f"{key}: no data sheet",
            ))
            if dividers:
                entries.append(_entry(
                    "shelf_pins", divider_part, what, positions=[], values=[], missing=_no_sheet(key),
                    counts={"shelf_pin_holes": None}, clauses=[], source_name=f"{key}: no data sheet",
                ))
            continue
        source, missing = sheet["source"], []
        raw = sheet.get("values") or {}
        by_name = {name: _value(raw, field, name, source, missing) for field, name in _PIN_FIELDS}
        positions, clauses, problem = [], [], None
        columns = {}
        for name, edge in (("front setback", "front edge"), ("rear setback", "rear edge")):
            form = by_name[name]["form"]
            columns[name] = form
            if form is not None:
                label = name.split()[0] + " column"
                positions.append({"label": label, "position": form, "from": edge})
                clauses.append(f"{label} {_say(form)} from the {edge}")
        # A divider stands on the bottom panel, so its holes sit one board lower from its own bottom end.
        divider_positions, divider_clauses = list(positions), list(clauses)
        t = spec["materials"][module["carcass"]]["thickness_mm"]
        pitch, first, last = (by_name[n]["form"] for n in ("pitch", "first hole", "last hole"))
        holes: int | None = None
        divider_holes: int | None = None
        if pitch and first and last:
            if all("mm" in f for f in (pitch, first, last)):
                top = module["height"] - t - last["mm"]
                heights, at = [], t + first["mm"]
                while at <= top + 1e-9:
                    heights.append(_num(at))
                    at += pitch["mm"]
                if heights:
                    for found, clause_list, offset in ((positions, clauses, 0), (divider_positions, divider_clauses, t)):
                        listed = [_num(h - offset) for h in heights]
                        found += [{"label": f"hole {i + 1}", "position": {"mm": h}, "from": "bottom end"}
                                  for i, h in enumerate(listed)]
                        shown = listed if len(listed) <= 4 else [*listed[:2], "…", listed[-1]]
                        clause_list.append("holes at " + ", ".join(h if h == "…" else _n(h) for h in shown) + " mm")
                    if all(columns.values()):
                        holes = 2 * 2 * len(heights)
                        divider_holes = 2 * 2 * len(heights) * dividers
                else:
                    problem = "no hole fits between the first and last hole heights"
            else:
                words = (
                    f"first hole {_say(first)} above the bottom shelf face, then every {_say(pitch)}, "
                    f"last hole at least {_say(last)} below the top"
                )
                for found, clause_list in ((positions, clauses), (divider_positions, divider_clauses)):
                    found.append({"label": "holes", "position": {"rule": words}, "from": "bottom end"})
                    clause_list.append(f"holes: {words}")
        for name in ("hole diameter", "hole depth", "pins per shelf"):
            form = by_name[name]["form"]
            if form is not None:
                said = f"{name} {_say(form)}" if name != "hole diameter" else f"hole Ø {_say(form)}"
                clauses.append(said)
                divider_clauses.append(said)
        entries.append(_entry(
            "shelf_pins", part, what, positions=positions, values=list(by_name.values()), missing=missing,
            problem=problem, counts={"shelf_pin_holes": holes}, clauses=["both sides, inner face"] + clauses,
            source_name=f"{key} data sheet",
        ))
        if dividers:
            entries.append(_entry(
                "shelf_pins", divider_part, what, positions=divider_positions, values=list(by_name.values()),
                missing=list(missing), problem=problem, counts={"shelf_pin_holes": divider_holes},
                clauses=[f"each of {dividers} dividers, both faces"] + divider_clauses,
                source_name=f"{key} data sheet",
            ))
    return entries


# Hinges.


def _cup_centre(edge: Form | None, diameter: Form | None) -> Form | None:
    if edge is None or diameter is None:
        return None
    if "mm" in diameter:
        return _shift(edge, diameter["mm"] / 2)
    return {"rule": f"cup edge distance {_say(edge)} plus half the cup Ø {_say(diameter)}"}


def _hinge_entries(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[DrillEntry]:
    entries = []
    for module in spec["modules"]:
        rects = front_layout(module)
        for index, front in enumerate(module["fronts"]):
            if front["type"] != "door":
                continue
            first = next(rect for rect in rects if rect["entry"] == index)
            doors = len([rect for rect in rects if rect["entry"] == index])
            key = front.get("hinge") or HINGE_ID
            part = f"{module['id']}-door-{index + 1}"
            sheet = _sheet(inputs, key)
            per_door, _ = _hinge_count(sheet, first["h"])
            borings = {"hinge_cup_borings": per_door * doors}
            what = "hinges"
            if sheet is None:
                entries.append(_entry(
                    "hinges", part, what, positions=[], values=[], missing=_no_sheet(key), counts=borings,
                    clauses=[], source_name=f"{key}: no data sheet",
                ))
                continue
            source, missing = sheet["source"], []
            raw = sheet.get("values") or {}
            by_name = {
                name: _value(raw, field, name, source, missing)
                for field, name in (
                    ("cup_diameter_mm", "cup Ø"), ("cup_depth_mm", "cup depth"),
                    ("cup_edge_distance_mm", "cup edge distance"), ("end_distance_mm", "end distance"),
                )
            }
            positions, clauses, problem = [], [], None
            end = by_name["end distance"]["form"]
            origins = ("door's bottom end", "door's top end")
            if end is not None:
                if 2 * _shortest(end) >= first["h"]:
                    problem = "door too short for the hinge end distance"
                else:
                    positions = _along(first["h"], per_door, end, origins)
                    clauses.append(_along_text("hinge", positions, origins))
            diameter, depth, edge = (by_name[n]["form"] for n in ("cup Ø", "cup depth", "cup edge distance"))
            if diameter is not None:
                clauses.append(f"cup Ø {_say(diameter)}")
            if depth is not None:
                clauses.append(f"{_say(depth)} deep")
            centre = _cup_centre(edge, diameter)
            if centre is not None:
                positions.append({"label": "cup centre", "position": centre, "from": "hinge edge"})
                clauses.append(f"centre {_say(centre)} from the hinge edge")
            if doors > 1:
                clauses.append("hinge edge is the outer edge of each door")
            entries.append(_entry(
                "hinges", part, what, positions=positions, values=list(by_name.values()), missing=missing,
                problem=problem, counts=borings, clauses=clauses, source_name=f"{key} data sheet",
            ))
            entries.extend(_plate_entries(module, part, first, per_door, end, sheet, key))
    return entries


def _plate_entries(
    module: Mapping[str, Any], door_part: str, door: Mapping[str, Any], per_door: int, end: Form | None,
    sheet: Mapping[str, Any], key: str,
) -> list[DrillEntry]:
    raw = sheet.get("values") or {}
    plate = raw.get("plate_item")
    if not plate:
        return []
    source, missing = sheet["source"], []
    by_name = {
        name: _value(raw, field, name, source, missing)
        for field, name in (("plate_setback_mm", "plate setback"), ("plate_hole_spacing_mm", "plate hole spacing"))
    }
    if end is None:
        missing.append("end distance")
    positions, clauses, problem = [], [], None
    if end is not None and 2 * _shortest(end) < door["h"]:
        z = door["z"]
        hinges = _along(door["h"], per_door, end, ("bottom", "top"))
        for hinge in hinges:
            at = hinge["position"]
            if "rule" in at:
                level = {"rule": "level with its hinge"}
            elif hinge["from"] == "top":
                level = {"min_mm": _num(z + door["h"] - at["max_mm"]), "max_mm": _num(z + door["h"] - at["min_mm"])}
            else:
                level = _shift(at, z)
            positions.append({"label": f"plate {hinge['label']}", "position": level, "from": "side's bottom end"})
        clauses.append("plates at " + "; ".join(f"{p['label']} {_say(p['position'])}" for p in positions))
    elif end is not None:
        problem = "door too short for the hinge end distance"
    setback = by_name["plate setback"]["form"]
    spacing = by_name["plate hole spacing"]["form"]
    if setback is not None:
        clauses.append(f"{_say(setback)} from the front edge")
    if spacing is not None:
        clauses.append(f"holes {_say(spacing)} apart")
    return [_entry(
        "hinges", f"{module['id']}-side", f"mounting plates for {door_part}", positions=positions,
        values=list(by_name.values()), missing=missing, problem=problem, counts={},
        clauses=["at the door's hinge edge"] + clauses, source_name=f"{key} data sheet",
    )]


# Wall-shelf brackets.


def _bracket_entries(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[DrillEntry]:
    entries = []
    for shelf in spec.get("wall_shelves") or []:
        plan = bracket_plan(shelf, inputs)
        part, what = shelf["id"], "brackets"
        origins = ("left end", "right end")
        counts = {"brackets": plan["count"]}
        if plan["owner"]:
            listed = shelf["bracket_positions_mm"]
            positions = [{"label": str(i + 1), "position": {"mm": p}, "from": origins[0]} for i, p in enumerate(listed)]
            entries.append(_entry(
                "brackets", part, what, positions=positions, values=[], missing=[], counts=counts,
                clauses=[f"brackets at {', '.join(str(p) for p in listed)} mm from the left end, set by the owner"],
                source_name="owner's positions",
            ))
            continue
        source = plan["source"] or {}
        label = f"{source.get('publication', 'bracket rules')}"
        values = []
        if plan["end"] is not None:
            values.append({"name": "bracket end distance", "form": plan["end"], "source": label})
        if plan["count"] is None:
            entries.append(_entry(
                "brackets", part, what, positions=[], values=values, missing=plan["missing"],
                problem=plan["problem"], counts=counts, clauses=[], source_name=label,
            ))
            continue
        positions = _along(shelf["length"], plan["count"], plan["end"], origins)
        entries.append(_entry(
            "brackets", part, what, positions=positions, values=values, missing=[], counts=counts,
            clauses=[_along_text("bracket", positions, origins)],
            source_name=label,
        ))
    return entries


CALCULATIONS: Final[tuple[Calculation, ...]] = (
    Calculation(
        "shelf_pins", "shelf_pin",
        tuple(name for _, name in _PIN_FIELDS), _shelf_pin_entries,
    ),
    Calculation(
        "hinges", "hinge",
        ("cup Ø", "cup depth", "cup edge distance", "end distance", "count table", "plate setback", "plate hole spacing"),
        _hinge_entries,
    ),
    Calculation(
        "brackets", "rules",
        (BRACKET_COUNT_CHECK, BRACKET_SPACING_CHECK), _bracket_entries,
    ),
)


def drilling(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The drilling list of a spec and its frozen inputs: entries, counts, warnings, completeness."""
    entries: list[DrillEntry] = []
    for calculation in CALCULATIONS:
        entries.extend(calculation.run(spec, inputs))
    counts: dict[str, int | None] = {"hinge_cup_borings": 0}
    for entry in entries:
        for name, value in entry["counts"].items():
            if name not in counts:
                counts[name] = value
            elif counts[name] is None or value is None:
                counts[name] = None
            else:
                counts[name] += value
    warnings = [warning for entry in entries for warning in _warning(entry)]
    return {
        "calculated": True, "complete": not warnings, "warnings": warnings, "counts": counts, "entries": entries,
    }


def drilling_lines(result: Mapping[str, Any] | None) -> list[str]:
    """A drilling list as plain lines for the agents; `None` is a version drilling was not calculated for."""
    if result is None:
        return ["Drilling: not calculated for this version."]
    lines = ["Drilling" + (" (complete):" if result["complete"] else " (INCOMPLETE):")]
    lines += [f"- {entry['text']}" for entry in result["entries"]]
    counts = result["counts"]
    work = [f"{counts['hinge_cup_borings']} hinge cup borings"]
    if "shelf_pin_holes" in counts:
        holes = counts["shelf_pin_holes"]
        work.append(f"{holes} shelf-pin holes" if holes is not None else "shelf-pin holes not counted")
    lines.append("Drilling work: " + ", ".join(work))
    lines += [f"Warning: {warning}" for warning in result["warnings"]]
    return lines


def derive(
    spec: Mapping[str, Any], inputs: Mapping[str, Any] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """(cut-list rows, hardware rows, assembly steps) for a normalised spec.

    Rows follow module order, then rule order within a module, then extra
    parts; hardware follows the order each id first appears. Part overrides
    are applied last. The same input always yields identical output.
    """
    parts, hardware = _rule_rows(spec, inputs)
    parts = _apply_overrides(parts, spec.get("part_overrides") or [])
    return parts, hardware, _assembly(spec)


def emitted_spec(spec: Mapping[str, Any], inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The `spec.json` a derived package publishes: the studio's one source.

    `modules` holds each module's box as numbers only (the studio's existing
    type), `fronts` every front rectangle in build coordinates, and `input`
    the normalised specification itself. `layers` is empty: a derived package
    has no model until the Phase 3 generator replaces this document.
    """
    parts, hardware, assembly = derive(spec, inputs)
    fronts: list[dict[str, Any]] = []
    for module in spec["modules"]:
        for rect in front_layout(module):
            fronts.append(
                {**rect, "module": module["id"], "x": module["x"] + rect["x"], "z": module["z"] + rect["z"]}
            )
    document = _emitted(spec, parts, hardware, assembly, fronts)
    if inputs is not None:
        document["drilling"] = drilling(spec, inputs)
    return document


def _emitted(
    spec: Mapping[str, Any], parts: list[dict[str, Any]], hardware: list[dict[str, Any]],
    assembly: list[dict[str, Any]], fronts: list[dict[str, Any]],
) -> dict[str, Any]:
    document = {
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
    for module in spec["modules"]:
        if module.get("adjustable_shelves"):
            document["modules"][module["id"]]["adjustable_shelves"] = module["adjustable_shelves"]
    if spec.get("wall_shelves"):
        document["wall_shelves"] = {
            shelf["id"]: {
                "x": shelf["x"], "y": shelf["y"], "z": shelf["z"], "l": shelf["length"], "d": shelf["depth"],
                "t": spec["materials"][shelf["material"]]["thickness_mm"],
            }
            for shelf in spec["wall_shelves"]
        }
    return document
