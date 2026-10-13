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

- sides: two, full height × (depth − b); with `side_folds`, the folded side is
  two rectangles (lower/upper along height, or front/back along depth) mitred
  at `angle_deg`, the other side one full-height (or full-depth) rectangle,
  ids `{id}-side-{left|right}` and `-lower`/`-upper` or `-front`/`-back`;
- top and bottom: two, between the sides, (width − 2t) × (depth − b); with a
  fold, each is cut to the smallest inner width along that board's thickness,
  as separate rows when the sizes differ;
- back: one, full width × full height in the back slot, fixed over the rear;
  with a fold, the net follows the side profile and the row is its
  grain-aligned bounding rectangle;
- fixed shelves: between the sides, (width − 2t) × (depth − b), or each board's
  own depth from `shelf_depths_mm` (null keeps the back-reduced depth) placed by
  `shelf_depth_align` (`back` default: rear on the inner rear; `front`: front on
  the side fronts); with a fold, each is cut to the smallest inner width along
  its thickness, one `{id}-shelf-{n}` row when the widths or depths differ,
  lowest first;
- shelf heights: evenly spaced, fixed shelves lowest; or, when stated, each
  underside at `shelf_positions_mm`, or one `shelf_spacing_mm` clear gap above
  the board below, measured from the top face of the bottom panel;
- shelf kinds: each shelf is fixed or adjustable by `shelf_kinds` (lowest
  first), else the fixed shelves are the lowest; kinds never move a shelf;
- dividers: `dividers` full-height boards between the top and bottom,
  (height − 2t) × (depth − b), splitting the inner width into bays (evenly,
  rounded down, or at `divider_positions_mm` from the left side's inner face);
  shelves then sit in every bay at the same heights, cut to the bay's width,
  one row while the bays share a width, else one `-bay-<n>` row per bay;
- dividers between named boards (`divider_spans`: the bottom or a fixed shelf
  up to a fixed shelf or the top, shelves counted from the lowest), or any
  dividers on a folded module: each divider is the clear gap between its two
  boards, floored; a shelf is split only by the dividers that cross its height;
  boards of one kind are grouped by cut width (`{id}-shelf` while one width,
  else `-<n>` from the lowest level, left to right) and dividers by length
  (`{id}-divider`, else `-<n>` from the left); unpositioned dividers on a fold
  split the narrowest opening along their spans into equal bays;
- fronts, stacked top to bottom in list order over the module's front face
  (an entry without a `height` shares what the others leave), each overlay
  with a 3 mm gap (1.5 mm at every edge):
  - doors split the entry's width; 2, 3 or 4 concealed hinges each for a door
    up to 900 mm, up to 1 600 mm, or taller; a push-latch door also gets one
    latch and no handle note;
  - drawers split the entry's height; each has a front, two sides, a back and a
    bottom, and one runner pair of the longest standard length that fits;
  - a flap covers the entry, with two flap hinges and a pair of stays;
  - with a height fold, each leaf's outer edge follows the folded silhouette;
    a rectangular net stays a rectangle; otherwise one n-gon whose cut-list
    row is the grain-aligned bounding rectangle with notes naming the net;
    two doors of one entry with different nets become `{id}-door-{entry}-1`
    and `-2` left to right, each qty 1; a drawer box stays a rectangle cut to
    the smallest inner width along that drawer's height, less runner clearance;
- adjustable shelves: one row between the sides at that shelf's depth (the
  back-reduced depth when unset), less `ADJUSTABLE_SHELF_CLEARANCE_MM` on the
  width (rounded down); pins per shelf times shelves of the module's shelf-pin
  item, or no quantity when its data sheet lacks the value; with a fold, each
  board is cut to the smallest inner width along its thickness, then the
  clearance, floored; an adjustable shelf with a custom depth must cover both
  pin columns when the sheet gives exact front and rear setbacks;
- hinges are keyed by the door's hinge item; the count per door is the item's
  own count table when its data sheet has one, else the height rule above; a
  data sheet that names a mounting-plate item adds one plate per hinge;
- confirmat screws: 8 per carcass plus 4 per fold joint plus 4 per fixed shelf
  board plus 4 per divider;
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


def shelf_kinds_of(module: Mapping[str, Any]) -> list[str]:
    """Each shelf's kind, lowest first: `shelf_kinds` when stated, else the fixed shelves lowest."""
    stated = module.get("shelf_kinds")
    if stated:
        return list(stated)
    return ["fixed"] * module["shelves"] + ["adjustable"] * module.get("adjustable_shelves", 0)


def shelf_levels(module: Mapping[str, Any], t: int) -> list[tuple[float, str]]:
    """Each shelf's centre above the module's bottom face and its kind, lowest first."""
    return list(zip(shelf_centres(module, t), shelf_kinds_of(module), strict=True))


def kind_centres(module: Mapping[str, Any], t: int, kind: str) -> list[float]:
    """The centres of the shelves of one kind, lowest first."""
    return [centre for centre, found in shelf_levels(module, t) if found == kind]


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


def round_half_away(value: float) -> int:
    """Nearest integer, halves away from zero (the fold inset and along-slope length)."""
    if value < 0:
        return -round_half_away(-value)
    return math.floor(value + 0.5)


def inset_mm(run: float, angle_deg: int) -> int:
    """Horizontal inset of a run past the kink, in whole millimetres."""
    if run <= 0:
        return 0
    return round_half_away(run * math.tan(math.radians(angle_deg)))


def slope_mm(run: float, angle_deg: int) -> int:
    """Along-slope length of a run past the kink, in whole millimetres."""
    if run <= 0:
        return 0
    return round_half_away(run / math.cos(math.radians(angle_deg)))


class SideFold(NamedTuple):
    side: str
    from_mm: int
    along: str
    angle_deg: int
    towards: str
    run_mm: int
    inset_mm: int
    slope_mm: int


class FoldProfile(NamedTuple):
    """A module's side folds and the AABB of the folded solid, in its own millimetre frame."""

    width: int
    height: int
    depth: int
    t: int
    b: int
    inner_d: int
    folds: tuple[SideFold, ...]
    x0: int
    y0: int
    z0: int
    w: int
    d: int
    h: int

    def fold_on(self, side: str) -> SideFold | None:
        return next((fold for fold in self.folds if fold.side == side), None)


def _outer_x_at(profile: FoldProfile, side: str, y: float, z: float) -> int:
    base = 0 if side == "left" else profile.width
    fold = profile.fold_on(side)
    if fold is None:
        return base
    position = z if fold.along == "height" else y
    inset = inset_mm(position - fold.from_mm, fold.angle_deg)
    toward_plus = (side == "left" and fold.towards == "inside") or (side == "right" and fold.towards == "outside")
    return base + inset if toward_plus else base - inset


def inner_left_x(profile: FoldProfile, y: float, z: float) -> int:
    return _outer_x_at(profile, "left", y, z) + profile.t


def inner_right_x(profile: FoldProfile, y: float, z: float) -> int:
    return _outer_x_at(profile, "right", y, z) - profile.t


def inner_width_at(profile: FoldProfile, y: float, z: float) -> int:
    return inner_right_x(profile, y, z) - inner_left_x(profile, y, z)


def min_inner_width(profile: FoldProfile, y0: float, y1: float, z0: float, z1: float) -> int:
    """Smallest inner width over a board's y and z ranges, a whole millimetre."""
    ys = {y0, y1}
    zs = {z0, z1}
    for fold in profile.folds:
        if fold.along == "depth" and y0 < fold.from_mm < y1:
            ys.add(float(fold.from_mm))
        if fold.along == "height" and z0 < fold.from_mm < z1:
            zs.add(float(fold.from_mm))
    return min(inner_width_at(profile, y, z) for y in ys for z in zs)


def back_outline(profile: FoldProfile) -> list[tuple[int, int]]:
    """(x, z) vertices of the back net, counter-clockwise in the back plane."""
    zs = [0, profile.height]
    for fold in profile.folds:
        if fold.along == "height":
            zs.append(fold.from_mm)
    zs = sorted(set(zs))
    y = float(profile.inner_d)
    left = [(_outer_x_at(profile, "left", y, z), z) for z in zs]
    right = [(_outer_x_at(profile, "right", y, z), z) for z in reversed(zs)]
    verts: list[tuple[int, int]] = []
    for vertex in left + right:
        if not verts or verts[-1] != vertex:
            verts.append(vertex)
    if len(verts) > 1 and verts[0] == verts[-1]:
        verts.pop()
    return verts


def _height_folds(profile: FoldProfile) -> tuple[SideFold, ...]:
    return tuple(fold for fold in profile.folds if fold.along == "height")


def _dedupe_verts(verts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for vertex in verts:
        if not out or out[-1] != vertex:
            out.append(vertex)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _is_axis_aligned_rectangle(net: list[tuple[float, float]]) -> bool:
    if len(net) != 4:
        return False
    return len({p[0] for p in net}) == 2 and len({p[1] for p in net}) == 2


def _leaf_edge_fns(
    profile: FoldProfile, x0: float, x1: float, *, warp_left: bool, warp_right: bool
) -> tuple[Callable[[float], float], Callable[[float], float]]:
    half = GAP_MM / 2

    def left_fn(z: float) -> float:
        if warp_left:
            return float(_outer_x_at(profile, "left", 0.0, z)) + half
        return x0

    def right_fn(z: float) -> float:
        if warp_right:
            return float(_outer_x_at(profile, "right", 0.0, z)) - half
        return x1

    return left_fn, right_fn


def _last_open_z(
    left_fn: Callable[[float], float],
    right_fn: Callable[[float], float],
    z0: float,
    z1: float,
) -> float | None:
    """Highest z in [z0, z1] where the leaf still has a positive width."""
    if left_fn(z0) >= right_fn(z0) - 1e-9:
        return None
    if left_fn(z1) < right_fn(z1) - 1e-9:
        return z1
    lo, hi = float(z0), float(z1)
    for _ in range(50):
        mid = (lo + hi) / 2
        if left_fn(mid) < right_fn(mid) - 1e-9:
            lo = mid
        else:
            hi = mid
    return lo


def _clip_samples(
    profile: FoldProfile,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    *,
    warp_left: bool,
    warp_right: bool,
) -> list[float]:
    """z samples for a leaf: unbent ends, kinks, and the last z with positive width."""
    left_fn, right_fn = _leaf_edge_fns(
        profile, x0, x1, warp_left=warp_left, warp_right=warp_right
    )
    zs = {z0, z1}
    for fold in _height_folds(profile):
        if z0 < fold.from_mm < z1:
            zs.add(float(fold.from_mm))
    open_z = _last_open_z(left_fn, right_fn, z0, z1)
    if open_z is not None:
        zs.add(open_z)
    return sorted(zs)


def _leaf_net(
    profile: FoldProfile,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    *,
    warp_left: bool,
    warp_right: bool,
) -> list[tuple[float, float]]:
    left_fn, right_fn = _leaf_edge_fns(
        profile, x0, x1, warp_left=warp_left, warp_right=warp_right
    )
    left_chain: list[tuple[float, float]] = []
    right_chain: list[tuple[float, float]] = []
    for z in _clip_samples(
        profile, x0, x1, z0, z1, warp_left=warp_left, warp_right=warp_right
    ):
        left, right = left_fn(z), right_fn(z)
        if left < right - 1e-9:
            left_chain.append((left, z))
            right_chain.append((right, z))
    return _dedupe_verts(left_chain + list(reversed(right_chain)))


def _bound_of(net: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in net]
    zs = [point[1] for point in net]
    x0, z0 = min(xs), min(zs)
    return x0, z0, max(xs) - x0, max(zs) - z0


def _refuse_pinched_front(
    profile: FoldProfile,
    x0: float,
    x1: float,
    z0: float,
    z1: float,
    *,
    warp_left: bool,
    warp_right: bool,
) -> None:
    left_fn, right_fn = _leaf_edge_fns(
        profile, x0, x1, warp_left=warp_left, warp_right=warp_right
    )
    samples = {0.0, float(profile.height)}
    for fold in _height_folds(profile):
        samples.add(float(fold.from_mm))
    for raw in samples:
        z = min(max(raw, z0), z1)
        width = right_fn(z) - left_fn(z)
        if 1e-9 < width < MIN_FRONT_MM:
            raise DeriveError(
                f"remaining front width {math.floor(width)} mm is below the minimum "
                f"front size of {MIN_FRONT_MM} mm"
            )


def _warp_front_layout(
    module: Mapping[str, Any], profile: FoldProfile, rects: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    left_fold = profile.fold_on("left")
    right_fold = profile.fold_on("right")
    has_left = left_fold is not None and left_fold.along == "height"
    has_right = right_fold is not None and right_fold.along == "height"
    if not has_left and not has_right:
        return rects
    by_entry: dict[int, list[int]] = {}
    for index, rect in enumerate(rects):
        by_entry.setdefault(rect["entry"], []).append(index)
    warped: list[dict[str, Any]] = []
    for index, rect in enumerate(rects):
        siblings = by_entry[rect["entry"]]
        pos = siblings.index(index)
        kind = rect["type"]
        warp_left = has_left and (kind != "door" or pos == 0)
        warp_right = has_right and (kind != "door" or pos == len(siblings) - 1)
        x0, x1 = rect["x"], rect["x"] + rect["w"]
        z0, z1 = rect["z"], rect["z"] + rect["h"]
        if warp_left or warp_right:
            _refuse_pinched_front(
                profile, x0, x1, z0, z1, warp_left=warp_left, warp_right=warp_right
            )
        if not warp_left and not warp_right:
            warped.append(rect)
            continue
        net = _leaf_net(
            profile, x0, x1, z0, z1, warp_left=warp_left, warp_right=warp_right
        )
        if len(net) < 3:
            raise DeriveError(
                f"remaining front width 0 mm is below the minimum front size of {MIN_FRONT_MM} mm"
            )
        bx, bz, bw, bh = _bound_of(net)
        if _is_axis_aligned_rectangle(net) and abs(bw - rect["w"]) < 1e-9 and abs(bh - rect["h"]) < 1e-9:
            warped.append(rect)
            continue
        leaf = dict(rect)
        leaf["net"] = tuple(net)
        leaf["rectangular"] = _is_axis_aligned_rectangle(net)
        leaf["x"], leaf["z"], leaf["w"], leaf["h"] = bx, bz, bw, bh
        warped.append(leaf)
    return warped


def fold_profile(module: Mapping[str, Any], t: int, b: int) -> FoldProfile:
    """The module's folds, or the unbent box when `side_folds` is empty.

    Raises `DeriveError` when two folds name the same side, `from_mm` sits inside
    a carcass panel, the far-end inset rounds to 0 mm, or the inner opening
    pinches below 1 mm.
    """
    width, height, depth = module["width"], module["height"], module["depth"]
    inner_d = depth - b
    raw = list(module.get("side_folds") or [])
    sides = [entry["side"] for entry in raw]
    if len(sides) != len(set(sides)):
        raise DeriveError("two folds name the same side")
    folds: list[SideFold] = []
    for entry in raw:
        along = entry["along"]
        from_mm = entry["from_mm"]
        angle = entry["angle_deg"]
        if along == "height":
            if not t < from_mm < height - t:
                raise DeriveError(
                    f"from_mm {from_mm} must lie strictly between the carcass thickness ({t} mm) "
                    f"and height minus that thickness ({height - t} mm)"
                )
            run = height - from_mm
        else:
            if not 1 < from_mm < inner_d:
                raise DeriveError(
                    f"from_mm {from_mm} must lie strictly between 1 mm and the back-reduced depth "
                    f"({inner_d} mm)"
                )
            run = inner_d - from_mm
        inset = inset_mm(run, angle)
        if inset == 0:
            raise DeriveError("inset at the far end rounds to 0 mm")
        folds.append(
            SideFold(
                side=entry["side"],
                from_mm=from_mm,
                along=along,
                angle_deg=angle,
                towards=entry["towards"],
                run_mm=run,
                inset_mm=inset,
                slope_mm=slope_mm(run, angle),
            )
        )
    xs = [0, width]
    ys = [0, depth]
    profile = FoldProfile(
        width=width, height=height, depth=depth, t=t, b=b, inner_d=inner_d,
        folds=tuple(folds), x0=0, y0=0, z0=0, w=width, d=depth, h=height,
    )
    if folds:
        remaining = min_inner_width(profile, 0, inner_d, 0, height)
        if remaining < 1:
            raise DeriveError(f"remaining inner width is {remaining} mm")
        for fold in folds:
            if fold.along == "height":
                xs.append(_outer_x_at(profile, fold.side, 0, height))
            else:
                xs.append(_outer_x_at(profile, fold.side, inner_d, 0))
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        profile = profile._replace(x0=x0, y0=y0, w=x1 - x0, d=y1 - y0)
    return profile


def module_bounds(module: Mapping[str, Any], t: int, b: int) -> tuple[int, int, int, int, int, int]:
    """The folded solid's AABB in the module's frame: (x0, y0, z0, w, d, h), including protruding shelves."""
    profile = fold_profile(module, t, b)
    x0, y0, z0 = float(profile.x0), float(profile.y0), float(profile.z0)
    x1, y1, z1 = x0 + profile.w, y0 + profile.d, z0 + profile.h
    if module.get("shelf_depths_mm") and (module.get("shelves") or module.get("adjustable_shelves")):
        for board in shelf_boards(module, t, b):
            y0 = min(y0, board.y0)
            y1 = max(y1, board.y0 + board.depth)
    return (
        math.floor(x0),
        math.floor(y0),
        math.floor(z0),
        math.ceil(x1 - x0),
        math.ceil(y1 - y0),
        math.ceil(z1 - z0),
    )


# --- dividers between named boards and shelves split where they cross (partial-and-folded-dividers) ---


class DividerPlace(NamedTuple):
    """One divider in the module's own millimetre frame: its left face, bottom and top, and its cut length."""

    left: float
    bottom: float
    top: float
    length: int


class ShelfBoard(NamedTuple):
    """One shelf board: its shelf number (from 1, lowest), kind, bay when its level is split, and cut."""

    level: int
    kind: str
    bay: int | None
    x0: float
    centre: float
    width: int
    depth: int
    y0: float


def shelf_depth_align_of(module: Mapping[str, Any]) -> str:
    """`back` or `front`; `back` when depths are unset or align is omitted."""
    return module.get("shelf_depth_align") or "back"


def shelf_depth_of(module: Mapping[str, Any], level: int, inner_d: int) -> int:
    """Cut depth for shelf `level` (1-based, lowest first): stated depth or the back-reduced default."""
    depths = module.get("shelf_depths_mm")
    if not depths:
        return inner_d
    stated = depths[level - 1]
    return inner_d if stated is None else stated


def shelf_y0(align: str, inner_d: int, depth: int) -> float:
    """Front face of a shelf board in the module frame from the flush align."""
    if align == "front":
        return 0.0
    return float(inner_d - depth)


def shelf_covers_pin_columns(y0: float, depth: int, inner_d: int, front_setback: float, rear_setback: float) -> bool:
    """Whether a placed shelf covers both pin columns (setbacks from front and rear edges)."""
    front_col = front_setback
    rear_col = inner_d - rear_setback
    return y0 <= front_col + 1e-9 and y0 + depth >= rear_col - 1e-9


def uses_divider_layout(module: Mapping[str, Any]) -> bool:
    """Whether the module's dividers need the span-aware layout: spans are stated, or the module is folded."""
    return bool(module.get("dividers")) and bool(module.get("divider_spans") or module.get("side_folds"))


def divider_ends(module: Mapping[str, Any], t: int) -> list[tuple[float, float]]:
    """Each divider's bottom and top above the module's bottom face, left to right."""
    centres = shelf_centres(module, t)
    count = module.get("dividers", 0)
    spans = module.get("divider_spans") or [{"from_board": "bottom", "to_board": "top"}] * count
    ends = []
    for span in spans:
        low, high = span["from_board"], span["to_board"]
        bottom = t if low == "bottom" else centres[low - 1] + t / 2
        top = module["height"] - t if high == "top" else centres[high - 1] - t / 2
        ends.append((bottom, top))
    return ends


def _board_samples(profile: FoldProfile, z0: float, z1: float) -> list[tuple[float, float]]:
    """The (y, z) points where a board spanning `z0`–`z1` and the full depth meets its extremes."""
    ys = {0.0, float(profile.inner_d)}
    zs = {float(z0), float(z1)}
    for fold in profile.folds:
        if fold.along == "depth" and 0 < fold.from_mm < profile.inner_d:
            ys.add(float(fold.from_mm))
        if fold.along == "height" and z0 < fold.from_mm < z1:
            zs.add(float(fold.from_mm))
    return [(y, z) for y in sorted(ys) for z in sorted(zs)]


def narrowest_opening(profile: FoldProfile, z0: float, z1: float) -> tuple[int, int]:
    """The inner left x and inner width where the opening between `z0` and `z1` is narrowest."""
    y_at, z_at = min(_board_samples(profile, z0, z1), key=lambda p: inner_width_at(profile, p[0], p[1]))
    return inner_left_x(profile, y_at, z_at), inner_width_at(profile, y_at, z_at)


def divider_places(module: Mapping[str, Any], t: int, b: int) -> list[DividerPlace]:
    """Every divider, left to right. Stated positions are measured from the unbent left side's inner face.

    Without positions the dividers split the inner width into equal bays, as `bays` does; on a folded
    module they split the narrowest opening found along their spans and the full depth.
    """
    ends = divider_ends(module, t)
    if not ends:
        return []
    count = len(ends)
    positions = module.get("divider_positions_mm")
    if positions:
        lefts: list[float] = [t + position for position in positions]
    elif module.get("side_folds"):
        low = min(bottom for bottom, _top in ends)
        high = max(top for _bottom, top in ends)
        opening_left, opening = narrowest_opening(fold_profile(module, t, b), low, high)
        bay = (opening - count * t) // (count + 1)
        lefts = [opening_left + k * (bay + t) + bay for k in range(count)]
    else:
        lefts = [t + left + width for left, width in bays(module, t)[:-1]]
    return [
        DividerPlace(left, bottom, top, math.floor(top - bottom + 1e-9))
        for left, (bottom, top) in zip(lefts, ends, strict=True)
    ]


def divider_fit_problem(module: Mapping[str, Any], t: int, b: int) -> str | None:
    """On a folded module, why a divider does not fit inside the folded opening, or `None`."""
    if not module.get("dividers") or not module.get("side_folds"):
        return None
    profile = fold_profile(module, t, b)
    for number, place in enumerate(divider_places(module, t, b), start=1):
        for y, z in _board_samples(profile, place.bottom, place.top):
            left, right = inner_left_x(profile, y, z), inner_right_x(profile, y, z)
            if place.left <= left:
                return (
                    f"divider {number} would cut into the folded left side at {_n(z)} mm "
                    f"(the inner face is {left - t} mm from the unbent one there)"
                )
            if place.left + t >= right:
                return (
                    f"divider {number} would cut into the folded right side at {_n(z)} mm "
                    f"(the inner face is {right - t} mm from the unbent left inner face there)"
                )
    return None


def shelf_boards(module: Mapping[str, Any], t: int, b: int) -> list[ShelfBoard]:
    """Every shelf board, lowest level first and left to right: a level is split only where a divider crosses it."""
    places = divider_places(module, t, b)
    profile = fold_profile(module, t, b) if module.get("side_folds") else None
    inner_d = profile.inner_d if profile is not None else module["depth"] - b
    align = shelf_depth_align_of(module)
    found = []
    for level, (centre, kind) in enumerate(shelf_levels(module, t), start=1):
        z0, z1 = centre - t / 2, centre + t / 2
        depth = shelf_depth_of(module, level, inner_d)
        y0 = shelf_y0(align, inner_d, depth)
        crossing = sorted((p for p in places if p.bottom < centre < p.top), key=lambda p: p.left)
        if profile is None:
            left_edge: float = t
            right_edge: float = module["width"] - t
        else:
            samples = _board_samples(profile, z0, z1)
            left_edge = max(inner_left_x(profile, y, z) for y, z in samples)
            right_edge = min(inner_right_x(profile, y, z) for y, z in samples)
        if not crossing:
            if profile is None:
                found.append(
                    ShelfBoard(level, kind, None, left_edge, centre, math.floor(right_edge - left_edge), depth, y0)
                )
            else:
                opening_left, _opening = narrowest_opening(profile, z0, z1)
                width = min_inner_width(profile, 0, profile.inner_d, z0, z1)
                found.append(ShelfBoard(level, kind, None, opening_left, centre, width, depth, y0))
            continue
        edges = [left_edge]
        for place in crossing:
            edges += [place.left, place.left + t]
        edges.append(right_edge)
        for bay, (start, end) in enumerate(zip(edges[::2], edges[1::2], strict=True), start=1):
            found.append(
                ShelfBoard(level, kind, bay, start, centre, math.floor(end - start + 1e-9), depth, y0)
            )
    return found


def board_cut_width(board: ShelfBoard) -> int:
    """A board's cut length along the module's width: an adjustable board less the clearance, floored."""
    if board.kind == "adjustable":
        return math.floor(board.width - ADJUSTABLE_SHELF_CLEARANCE_MM)
    return board.width


def _where(boards: list[ShelfBoard]) -> str:
    """The shelf levels and bays a group of boards covers, in words."""
    by_level: dict[int, list[int]] = {}
    for board in boards:
        by_level.setdefault(board.level, [])
        if board.bay is not None:
            by_level[board.level].append(board.bay)
    parts = []
    for level, bays_of in by_level.items():
        if not bays_of:
            parts.append(f"shelf {level}")
        else:
            noun = "bay" if len(bays_of) == 1 else "bays"
            parts.append(f"shelf {level} {noun} {', '.join(str(bay) for bay in bays_of)}")
    return "; ".join(parts)


def shelf_rows(module: Mapping[str, Any], t: int, b: int) -> list[tuple[str, str, str, int, int, list[ShelfBoard]]]:
    """Shelf rows: (id, name, kind, cut width, cut depth, boards), grouped by (width, depth).

    One (width, depth) of a kind keeps `{id}-shelf` / `{id}-adjustable-shelf`; several become `-<n>`,
    numbered by first appearance from the lowest level and, within a level, from the left.
    """
    mid = module["id"]
    rows = []
    for kind, prefix, name in (
        ("fixed", f"{mid}-shelf", "Fixed shelf"),
        ("adjustable", f"{mid}-adjustable-shelf", "Adjustable shelf"),
    ):
        groups: dict[tuple[int, int], list[ShelfBoard]] = {}
        for board in shelf_boards(module, t, b):
            if board.kind == kind:
                groups.setdefault((board_cut_width(board), board.depth), []).append(board)
        if len(groups) == 1:
            (((width, depth), boards),) = groups.items()
            rows.append((prefix, name, kind, width, depth, boards))
            continue
        for number, ((width, depth), boards) in enumerate(groups.items(), start=1):
            rows.append((f"{prefix}-{number}", f"{name} {number}", kind, width, depth, boards))
    return rows


def divider_rows(module: Mapping[str, Any], t: int, b: int) -> list[tuple[str, int, list[DividerPlace]]]:
    """The dividers as cut-list rows: (id, length, dividers), one row while they share a length."""
    mid = module["id"]
    groups: dict[int, list[DividerPlace]] = {}
    for place in divider_places(module, t, b):
        groups.setdefault(place.length, []).append(place)
    if len(groups) <= 1:
        return [(f"{mid}-divider", length, places) for length, places in groups.items()]
    return [(f"{mid}-divider-{n}", length, places) for n, (length, places) in enumerate(groups.items(), start=1)]


def span_words(module: Mapping[str, Any]) -> list[str]:
    """Each divider's span in words, e.g. "from shelf 4 to the top", left to right; [] without spans."""
    words = []
    for span in module.get("divider_spans") or []:
        low = "the bottom" if span["from_board"] == "bottom" else f"shelf {span['from_board']}"
        high = "the top" if span["to_board"] == "top" else f"shelf {span['to_board']}"
        words.append(f"from {low} to {high}")
    return words


def widest_shelf_board(module: Mapping[str, Any], t: int, b: int) -> ShelfBoard | None:
    """The span-aware layout's widest shelf board (before the adjustable clearance), first found on a tie."""
    boards = shelf_boards(module, t, b)
    return max(boards, key=lambda board: board.width) if boards else None


def _carcass_tb(module: Mapping[str, Any], materials: Mapping[str, Mapping[str, Any]]) -> tuple[int, int]:
    t = materials[module["carcass"]]["thickness_mm"]
    b = materials[module["back"]]["thickness_mm"] if module.get("back") is not None else 0
    return t, b


def overall(spec: Mapping[str, Any]) -> dict[str, int]:
    """The build's overall width, height and depth: its envelope, or its modules' bounds."""
    envelope = spec.get("envelope")
    if envelope is not None:
        return {"w": envelope["width"], "h": envelope["height"], "d": envelope["depth"]}
    materials = spec.get("materials") or {}
    boxes = []
    for module in spec["modules"]:
        t, b = _carcass_tb(module, materials)
        x0, y0, z0, w, d, h = module_bounds(module, t, b)
        boxes.append((module["x"] + x0, module["y"] + y0, module["z"] + z0, w, d, h))
    for shelf in spec.get("wall_shelves") or []:
        thickness = materials[shelf["material"]]["thickness_mm"]
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


def front_layout(
    module: Mapping[str, Any], t: int | None = None, b: int | None = None
) -> list[dict[str, Any]]:
    """Every front leaf of one module, in the module's own front-face frame.

    `x` runs from the module's left face and `z` from its bottom face; each
    entry is one front panel with its size, type and the entry it came from.
    A folded height-fold leaf whose outline is not a rectangle also carries
    `net` (front-plane vertices) and `rectangular` False; `x`/`z`/`w`/`h`
    are then the axis-aligned bounds of that net.
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
    if module.get("side_folds"):
        if t is None:
            raise DeriveError("front_layout needs carcass thickness to fold a front")
        rects = _warp_front_layout(module, fold_profile(module, t, b or 0), rects)
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


def _folded_shelf_widths(module: Mapping[str, Any], profile: FoldProfile) -> list[int]:
    """Each fixed shelf's cut width, lowest first, on a folded module."""
    t = profile.t
    widths = []
    for centre in kind_centres(module, t, "fixed"):
        widths.append(min_inner_width(profile, 0, profile.inner_d, centre - t / 2, centre + t / 2))
    return widths


def _folded_adjustable_widths(module: Mapping[str, Any], profile: FoldProfile) -> list[int]:
    """Each adjustable shelf's cut width, lowest first: min inner, then clearance, floored."""
    t = profile.t
    widths = []
    for centre in kind_centres(module, t, "adjustable"):
        inner = min_inner_width(profile, 0, profile.inner_d, centre - t / 2, centre + t / 2)
        widths.append(math.floor(inner - ADJUSTABLE_SHELF_CLEARANCE_MM))
    return widths


def _leaf_key(leaf: Mapping[str, Any]) -> tuple[Any, ...]:
    if leaf.get("rectangular", True) and "net" not in leaf:
        return ("rect", leaf["w"], leaf["h"])
    if leaf.get("rectangular", True):
        return ("rect", math.floor(leaf["w"]), math.floor(leaf["h"]))
    net = tuple((round(x, 3), round(z, 3)) for x, z in leaf["net"])
    return ("net", net, math.floor(leaf["w"]), math.floor(leaf["h"]))


def _group_leaves(prefix: str, leaves: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """One row while nets match; otherwise `{prefix}-1` … left to right, qty 1 each."""
    if len(leaves) <= 1 or all(_leaf_key(leaf) == _leaf_key(leaves[0]) for leaf in leaves):
        return [(prefix, leaves)]
    return [(f"{prefix}-{n}", [leaf]) for n, leaf in enumerate(leaves, start=1)]


def _net_note(profile: FoldProfile, kind: str, extra: str) -> str:
    folds = ", ".join(
        f"{fold.side} {fold.angle_deg}° from {fold.from_mm} mm" for fold in profile.folds
    )
    return f"Rule: bounding rectangle of the {kind} net; outline follows the side profile {folds}{extra}"


def _drawer_box_width(
    profile: FoldProfile | None, inner_w: int, rect: Mapping[str, Any]
) -> int:
    if profile is None:
        return inner_w - 2 * DRAWER_SIDE_CLEARANCE_MM
    inner = min_inner_width(profile, 0, profile.inner_d, rect["z"], rect["z"] + rect["h"])
    return inner - 2 * DRAWER_SIDE_CLEARANCE_MM


def _cut_wh(leaf: Mapping[str, Any], *, vertical: bool) -> tuple[int, int]:
    """Cut-list (l, w); grain-aligned bounding rectangle, sizes rounded down."""
    if leaf.get("rectangular", True) and "net" not in leaf:
        return (leaf["h"], leaf["w"]) if vertical else (leaf["w"], leaf["h"])
    height, width = math.floor(leaf["h"]), math.floor(leaf["w"])
    return (height, width) if vertical else (width, height)


def _add_front_rows(
    rows: list[dict[str, Any]],
    module: Mapping[str, Any],
    hardware: _Hardware,
    t: int,
    b: int,
    material: str,
    bottom_slot: Mapping[str, Any],
    inner_w: int,
    inner_d: int,
    inputs: Mapping[str, Any] | None,
    profile: FoldProfile | None,
) -> None:
    mid = module["id"]
    rects = front_layout(module, t, b)
    for index, front in enumerate(module["fronts"]):
        entry = [rect for rect in rects if rect["entry"] == index]
        prefix = f"{mid}-{front['type']}-{index + 1}"
        if front["type"] == "door":
            push = front["opening"] == "push_latch"
            handle = (
                "; push-latch, no handle" if push else "; handle as specified"
            )
            for part_id, leaves in _group_leaves(prefix, entry):
                first = leaves[0]
                qty = len(leaves)
                length, width = _cut_wh(first, vertical=True)
                if first.get("rectangular", True) and "net" not in first:
                    notes = f"Rule: overlay door, 3 mm gap{handle}"
                else:
                    notes = _net_note(profile, "door", handle) if profile else f"Rule: overlay door, 3 mm gap{handle}"
                rows.append(
                    _part(
                        part_id, "Door", qty=qty, l=length, w=width, t=t, material=material,
                        grain="length (vertical)", banding="all edges", notes=notes, module=mid,
                    )
                )
                _hinge_lines(front, length, qty, inputs, hardware)
                if push:
                    hardware.add(PUSH_LATCH_ID, "Push latch", qty, "Rule: one per push-latch door")
        elif front["type"] == "drawer":
            runner = runner_length(inner_d)
            if runner is None:
                raise DeriveError(f"module {mid!r} is too shallow for a drawer runner")
            for part_id, leaves in _group_leaves(f"{prefix}-front", entry):
                first = leaves[0]
                qty = len(leaves)
                length, width = _cut_wh(first, vertical=False)
                if first.get("rectangular", True) and "net" not in first:
                    notes = "Rule: overlay drawer front, 3 mm gap"
                else:
                    notes = _net_note(profile, "drawer front", "") if profile else "Rule: overlay drawer front, 3 mm gap"
                rows.append(
                    _part(
                        part_id, "Drawer front", qty=qty, l=length, w=width, t=t,
                        material=material, grain="length (left-right)", banding="all edges",
                        notes=notes, module=mid,
                    )
                )
            box_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
            for rect in entry:
                box_w = _drawer_box_width(profile, inner_w, rect)
                box_h = math.floor(rect["h"]) - DRAWER_BOX_HEIGHT_REDUCTION_MM
                box_groups.setdefault((box_w, box_h), []).append(rect)
            split_box = len(box_groups) > 1
            for box_index, ((box_w, box_h), group) in enumerate(box_groups.items(), start=1):
                qty = len(group)
                suffix = f"-{box_index}" if split_box else ""
                rows.extend(
                    [
                        _part(
                            f"{prefix}-side{suffix}", "Drawer side", qty=2 * qty, l=runner, w=box_h, t=t,
                            material=material, grain="length (front-back)", banding="top edge",
                            notes=f"Rule: runner length × front height less {DRAWER_BOX_HEIGHT_REDUCTION_MM} mm",
                            module=mid,
                        ),
                        _part(
                            f"{prefix}-back{suffix}", "Drawer back", qty=qty, l=box_w - 2 * t, w=box_h, t=t,
                            material=material, grain="length (left-right)", banding="top edge",
                            notes="Rule: between the drawer sides", module=mid,
                        ),
                        _part(
                            f"{prefix}-bottom{suffix}", "Drawer bottom", qty=qty, l=runner, w=box_w,
                            t=bottom_slot["thickness_mm"], material=bottom_slot["material"],
                            grain="none", banding="none",
                            notes="Rule: full box width × runner length, fixed under the sides", module=mid,
                        ),
                    ]
                )
            hardware.add(
                f"drawer-runner-{runner}",
                f"Drawer runner pair, {runner} mm",
                len(entry),
                "Rule: one pair per drawer, longest standard length that fits",
            )
        else:  # flap
            first = entry[0]
            length, width = _cut_wh(first, vertical=False)
            hinged = f"{front['hinged']}-hinged overlay flap, 3 mm gap"
            if first.get("rectangular", True) and "net" not in first:
                notes = f"Rule: {hinged}"
            elif profile is not None:
                notes = _net_note(profile, "flap", f"; {hinged}")
            else:
                notes = f"Rule: {hinged}"
            rows.append(
                _part(
                    prefix, "Flap", qty=1, l=length, w=width, t=t, material=material,
                    grain="length (left-right)", banding="all edges", notes=notes, module=mid,
                )
            )
            hardware.add(FLAP_HINGE_ID, "Flap hinge", 2, "Rule: two per flap")
            hardware.add(FLAP_STAY_ID, "Flap stay", 2, "Rule: one pair per flap")


def _divider_layout_rows(
    module: Mapping[str, Any],
    hardware: _Hardware,
    t: int,
    b: int,
    material: str,
    inner_d: int,
    n_folds: int,
    inputs: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Divider and shelf rows, confirmats and pins for dividers between named boards or on a folded module."""
    mid = module["id"]
    rows = []
    spans = span_words(module)
    for row_id, length, places in divider_rows(module, t, b):
        where = "between the top and bottom" if not spans else "between the boards each divider names"
        rows.append(
            _part(
                row_id, "Divider", qty=len(places), l=length, w=inner_d, t=t, material=material,
                grain="length (vertical)", banding="front edge",
                notes=f"Rule: dividers {where} at the back-reduced depth", module=mid,
            )
        )
    fixed_boards = 0
    adjustable_boards = 0
    for row_id, name, kind, width, depth, boards in shelf_rows(module, t, b):
        if kind == "fixed":
            fixed_boards += len(boards)
            rule = "fixed shelf boards between the sides and the dividers that cross them"
        else:
            adjustable_boards += len(boards)
            rule = (
                f"adjustable shelf boards between the sides and the dividers that cross them, less "
                f"{ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance (rounded down)"
            )
        depth_note = f" at {depth} mm depth" if depth != inner_d else " at the back-reduced depth"
        rows.append(
            _part(
                row_id, name, qty=len(boards), l=width, w=depth, t=t, material=material,
                grain="length (left-right)", banding="front edge",
                notes=f"Rule: {rule}{depth_note}; {_where(boards)}", module=mid,
            )
        )
    dividers = module.get("dividers", 0)
    fold_words = " plus 4 per fold joint" if n_folds else ""
    hardware.add(
        CONFIRMAT_ID,
        "Confirmat screw 7×50 mm",
        8 + 4 * n_folds + 4 * fixed_boards + 4 * dividers,
        f"Rule: 8 per carcass{fold_words} plus 4 per fixed shelf board plus 4 per divider",
    )
    if adjustable_boards:
        _pin_line(module, adjustable_boards, inputs, hardware)
    return rows


def widest_shelf_span(module: Mapping[str, Any], t: int, b: int) -> int:
    """The shelf-span check's width: widest bay, unbent inner, or the widest folded shelf cut."""
    if uses_divider_layout(module):
        board = widest_shelf_board(module, t, b)
        return board.width if board is not None else module["width"] - 2 * t
    if module.get("dividers"):
        return max(bay_cut_widths(module, t))
    inner = module["width"] - 2 * t
    folds = module.get("side_folds") or []
    if not folds or not any(entry.get("towards") == "outside" for entry in folds):
        return inner
    widths = _folded_shelf_widths(module, fold_profile(module, t, b))
    return max(widths) if widths else inner


def _folded_module_rows(
    module: Mapping[str, Any],
    materials: Mapping[str, Mapping[str, Any]],
    hardware: _Hardware,
    t: int,
    b: int,
    material: str,
    back: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Cut-list rows for a module with `side_folds`."""
    mid = module["id"]
    profile = fold_profile(module, t, b)
    inner_d = profile.inner_d
    rows: list[dict[str, Any]] = []

    def carcass_part(identifier: str, name: str, *, qty: int, l: int, w: int, notes: str) -> dict[str, Any]:
        return _part(
            identifier, name, qty=qty, l=l, w=w, t=t, material=material,
            grain="length (vertical)" if "side" in identifier else "length (left-right)",
            banding="front edge", notes=notes, module=mid,
        )

    for side in ("left", "right"):
        fold = profile.fold_on(side)
        if fold is None:
            rows.append(
                carcass_part(
                    f"{mid}-side-{side}", f"Side, {side}", qty=1, l=profile.height, w=inner_d,
                    notes="Rule: full height × depth less the back",
                )
            )
            continue
        mitre = f"joining edge mitred {fold.angle_deg}°"
        if fold.along == "height":
            rows.append(
                carcass_part(
                    f"{mid}-side-{side}-lower", f"Side, {side} lower", qty=1, l=fold.from_mm, w=inner_d,
                    notes=f"Rule: {side} side to {fold.from_mm} mm; {mitre}",
                )
            )
            rows.append(
                carcass_part(
                    f"{mid}-side-{side}-upper", f"Side, {side} upper", qty=1, l=fold.slope_mm, w=inner_d,
                    notes=f"Rule: {side} side along the {fold.angle_deg}° slope from {fold.from_mm} mm; {mitre}",
                )
            )
        else:
            rows.append(
                carcass_part(
                    f"{mid}-side-{side}-front", f"Side, {side} front", qty=1, l=profile.height, w=fold.from_mm,
                    notes=f"Rule: {side} side to {fold.from_mm} mm along depth; {mitre}",
                )
            )
            rows.append(
                carcass_part(
                    f"{mid}-side-{side}-back", f"Side, {side} back", qty=1, l=profile.height, w=fold.slope_mm,
                    notes=f"Rule: {side} side along the {fold.angle_deg}° slope from {fold.from_mm} mm; {mitre}",
                )
            )

    bottom_w = min_inner_width(profile, 0, inner_d, 0, t)
    top_w = min_inner_width(profile, 0, inner_d, profile.height - t, profile.height)
    if bottom_w == top_w:
        rows.append(
            carcass_part(
                f"{mid}-top-bottom", "Top/bottom", qty=2, l=bottom_w, w=inner_d,
                notes="Rule: top and bottom between the sides",
            )
        )
    else:
        rows.append(
            carcass_part(
                f"{mid}-bottom", "Bottom", qty=1, l=bottom_w, w=inner_d,
                notes="Rule: bottom between the sides at the unbent inner width",
            )
        )
        rows.append(
            carcass_part(
                f"{mid}-top", "Top", qty=1, l=top_w, w=inner_d,
                notes="Rule: top between the sides at the smallest inner width along its thickness",
            )
        )

    if back is not None:
        outline = back_outline(profile)
        bound_w = max(x for x, _z in outline) - min(x for x, _z in outline)
        rows.append(
            _part(
                f"{mid}-back", "Back", qty=1, l=profile.height, w=bound_w, t=b, material=back["material"],
                grain="length (vertical)", banding="none",
                notes=(
                    "Rule: bounding rectangle of the back net; outline follows the side profile "
                    + ", ".join(
                        f"{fold.side} {fold.angle_deg}° from {fold.from_mm} mm" for fold in profile.folds
                    )
                ),
                module=mid,
            )
        )

    if module.get("dividers"):
        rows += _divider_layout_rows(module, hardware, t, b, material, inner_d, len(profile.folds), inputs)
        bottom_slot = back if back is not None else {"thickness_mm": t, "material": material}
        _add_front_rows(
            rows, module, hardware, t, b, material, bottom_slot, profile.width - 2 * t, inner_d, inputs, profile,
        )
        hardware.free(module.get("hardware") or [])
        return rows

    n_folds = len(profile.folds)
    if module.get("shelf_depths_mm"):
        fixed_boards = 0
        adjustable_boards = 0
        for row_id, name, kind, width, depth, boards in shelf_rows(module, t, b):
            if kind == "fixed":
                fixed_boards += len(boards)
                rule = "fixed shelf between the sides at the smallest inner width along its thickness"
            else:
                adjustable_boards += len(boards)
                rule = (
                    f"between the sides at the smallest inner width along its thickness, "
                    f"less {ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance (rounded down)"
                )
            depth_note = f" at {depth} mm depth" if depth != inner_d else ""
            rows.append(
                carcass_part(
                    row_id, name, qty=len(boards), l=width, w=depth,
                    notes=f"Rule: {rule}{depth_note}; {_where(boards)}",
                )
            )
        hardware.add(
            CONFIRMAT_ID,
            "Confirmat screw 7×50 mm",
            8 + 4 * n_folds + 4 * fixed_boards,
            "Rule: 8 per carcass plus 4 per fold joint plus 4 per fixed shelf board",
        )
        if adjustable_boards:
            _pin_line(module, adjustable_boards, inputs, hardware)
    else:
        shelf_widths = _folded_shelf_widths(module, profile)
        if shelf_widths:
            if len(set(shelf_widths)) == 1:
                rows.append(
                    carcass_part(
                        f"{mid}-shelf", "Fixed shelf", qty=len(shelf_widths), l=shelf_widths[0], w=inner_d,
                        notes="Rule: fixed shelves between the sides at the smallest inner width along each board",
                    )
                )
            else:
                for index, width in enumerate(shelf_widths, start=1):
                    rows.append(
                        carcass_part(
                            f"{mid}-shelf-{index}", f"Fixed shelf {index}", qty=1, l=width, w=inner_d,
                            notes="Rule: fixed shelf between the sides at the smallest inner width along its thickness",
                        )
                    )

        hardware.add(
            CONFIRMAT_ID,
            "Confirmat screw 7×50 mm",
            8 + 4 * n_folds + 4 * len(shelf_widths),
            "Rule: 8 per carcass plus 4 per fold joint plus 4 per fixed shelf board",
        )
        adjustable_widths = _folded_adjustable_widths(module, profile)
        if adjustable_widths:
            if len(set(adjustable_widths)) == 1:
                rows.append(
                    carcass_part(
                        f"{mid}-adjustable-shelf", "Adjustable shelf",
                        qty=len(adjustable_widths), l=adjustable_widths[0], w=inner_d,
                        notes=(
                            f"Rule: between the sides at the smallest inner width along each board, "
                            f"less {ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance (rounded down)"
                        ),
                    )
                )
            else:
                for index, width in enumerate(adjustable_widths, start=1):
                    rows.append(
                        carcass_part(
                            f"{mid}-adjustable-shelf-{index}", f"Adjustable shelf {index}",
                            qty=1, l=width, w=inner_d,
                            notes=(
                                f"Rule: between the sides at the smallest inner width along its thickness, "
                                f"less {ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance (rounded down)"
                            ),
                        )
                    )
            _pin_line(module, len(adjustable_widths), inputs, hardware)
    bottom_slot = back if back is not None else {"thickness_mm": t, "material": material}
    _add_front_rows(
        rows, module, hardware, t, b, material, bottom_slot, profile.width - 2 * t, inner_d, inputs, profile,
    )
    hardware.free(module.get("hardware") or [])
    return rows


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
    if module.get("side_folds"):
        return _folded_module_rows(module, materials, hardware, t, b, material, back, inputs)

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
    if uses_divider_layout(module):
        rows += _divider_layout_rows(module, hardware, t, b, material, inner_d, 0, inputs)
        bottom_slot = back if back is not None else carcass
        _add_front_rows(rows, module, hardware, t, b, material, bottom_slot, inner_w, inner_d, inputs, None)
        hardware.free(module.get("hardware") or [])
        return rows
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
    adjustable = module.get("adjustable_shelves", 0)
    if module.get("shelf_depths_mm"):
        fixed_boards = 0
        adjustable_boards = 0
        for row_id, name, kind, width, depth, boards in shelf_rows(module, t, b):
            if kind == "fixed":
                fixed_boards += len(boards)
                rule = "fixed shelf boards between the sides"
                if dividers:
                    rule += " and the dividers that cross them"
            else:
                adjustable_boards += len(boards)
                rule = (
                    f"adjustable shelf boards between the sides"
                    f"{' and the dividers that cross them' if dividers else ''}, less "
                    f"{ADJUSTABLE_SHELF_CLEARANCE_MM:g} mm clearance (rounded down)"
                )
            depth_note = f" at {depth} mm depth" if depth != inner_d else " at the back-reduced depth"
            rows.append(
                _part(
                    row_id, name, qty=len(boards), l=width, w=depth, t=t, material=material,
                    grain="length (left-right)", banding="front edge",
                    notes=f"Rule: {rule}{depth_note}; {_where(boards)}", module=mid,
                )
            )
        if adjustable_boards:
            _pin_line(module, adjustable_boards, inputs, hardware)
        if dividers:
            hardware.add(
                CONFIRMAT_ID,
                "Confirmat screw 7×50 mm",
                8 + 4 * fixed_boards + 4 * dividers,
                "Rule: 8 per carcass plus 4 per fixed shelf board plus 4 per divider",
            )
        else:
            hardware.add(
                CONFIRMAT_ID,
                "Confirmat screw 7×50 mm",
                8 + 4 * fixed_boards,
                "Rule: 8 per carcass plus 4 per fixed shelf",
            )
    else:
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

    bottom_slot = back if back is not None else carcass
    _add_front_rows(
        rows, module, hardware, t, b, material, bottom_slot, inner_w, inner_d, inputs, None,
    )
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


def check_adjustable_shelf_depths(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> None:
    """Refuse an adjustable shelf whose custom depth misses an exact pin column.

    Raises `DeriveError` naming `shelf_depths_mm` and the shelf number.
    """
    materials = spec.get("materials") or {}
    for index, module in enumerate(spec["modules"]):
        if not module.get("shelf_depths_mm") or not module.get("adjustable_shelves"):
            continue
        key = module.get("shelf_pin") or SHELF_PIN_ID
        sheet = _sheet(inputs, key)
        if sheet is None:
            continue
        raw = sheet.get("values") or {}
        front_form, rear_form = _form(raw.get("front_setback_mm")), _form(raw.get("rear_setback_mm"))
        if front_form is None or rear_form is None or "mm" not in front_form or "mm" not in rear_form:
            continue
        front, rear = float(front_form["mm"]), float(rear_form["mm"])
        t, b = _carcass_tb(module, materials)
        inner_d = module["depth"] - b
        for board in shelf_boards(module, t, b):
            if board.kind != "adjustable":
                continue
            if shelf_covers_pin_columns(board.y0, board.depth, inner_d, front, rear):
                continue
            raise DeriveError(
                f"modules[{index}].shelf_depths_mm: shelf {board.level} does not cover both shelf-pin columns "
                f"(front setback {front:g} mm, rear setback {rear:g} mm)"
            )


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
            spans = span_words(module)
            if spans:
                body += ", then the dividers (" + "; ".join(
                    f"divider {n} {words}" for n, words in enumerate(spans, start=1)
                ) + ")"
            else:
                body += f", then the {module['dividers']} dividers between them"
        if module["shelves"]:
            body += f", then the {module['shelves']} fixed shelves"
        body += "."
        if module.get("adjustable_shelves"):
            body += f" Fit the {module['adjustable_shelves']} adjustable shelves on shelf pins in the drilled holes."
        if module.get("back") is not None:
            body += " Square the carcass and fix the back over its rear."
        for fold in module.get("side_folds") or []:
            body += (
                f" Mitre the {fold['side']} side at {fold['angle_deg']}° from {fold['from_mm']} mm "
                f"along {fold['along']}."
            )
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


def _side_segments(module: Mapping[str, Any], spec: Mapping[str, Any]) -> list[tuple[str, str, SideFold | None]]:
    """Unique (part_id, segment, fold) for a module's side boards, left then right.

    `segment` is '' for an unfolder board, or lower/upper/front/back. A module
    with no folds yields one `{id}-side` row covering both sides.
    """
    mid = module["id"]
    folds = module.get("side_folds") or []
    if not folds:
        return [(f"{mid}-side", "", None)]
    t, b = _carcass_tb(module, spec["materials"])
    profile = fold_profile(module, t, b)
    found: list[tuple[str, str, SideFold | None]] = []
    seen: set[str] = set()
    for side in ("left", "right"):
        fold = profile.fold_on(side)
        if fold is None:
            parts = [(f"{mid}-side-{side}", "", None)]
        elif fold.along == "height":
            parts = [
                (f"{mid}-side-{side}-lower", "lower", fold),
                (f"{mid}-side-{side}-upper", "upper", fold),
            ]
        else:
            parts = [
                (f"{mid}-side-{side}-front", "front", fold),
                (f"{mid}-side-{side}-back", "back", fold),
            ]
        for part, segment, owned in parts:
            if part not in seen:
                seen.add(part)
                found.append((part, segment, owned))
    return found


def _holes_on_segment(
    heights: list[float], fold: SideFold | None, segment: str
) -> list[float]:
    if not fold or not segment:
        return heights
    if fold.along == "height":
        if segment == "lower":
            return [h for h in heights if h < fold.from_mm]
        return [
            float(slope_mm(h - fold.from_mm, fold.angle_deg))
            for h in heights
            if h >= fold.from_mm
        ]
    return heights


def _shelf_pin_entries(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[DrillEntry]:
    entries = []
    for module in spec["modules"]:
        if not module.get("adjustable_shelves"):
            continue
        key = module.get("shelf_pin") or SHELF_PIN_ID
        side_parts = _side_segments(module, spec)
        what = "shelf-pin holes"
        sheet = _sheet(inputs, key)
        t = spec["materials"][module["carcass"]]["thickness_mm"]
        targets = _pin_divider_rows(module, spec, t)
        if sheet is None:
            for part, _segment, _fold in side_parts:
                entries.append(_entry(
                    "shelf_pins", part, what, positions=[], values=[], missing=_no_sheet(key),
                    counts={"shelf_pin_holes": None}, clauses=[], source_name=f"{key}: no data sheet",
                ))
            for part, _count, _bottom, _top in targets:
                entries.append(_entry(
                    "shelf_pins", part, what, positions=[], values=[], missing=_no_sheet(key),
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
        # A divider's holes are measured from its own bottom end, on the board it stands on.
        divider_base, divider_clauses = list(positions), list(clauses)
        holes_clause_at = len(divider_clauses)
        pitch, first, last = (by_name[n]["form"] for n in ("pitch", "first hole", "last hole"))
        holes: int | None = None
        if pitch and first and last:
            if all("mm" in f for f in (pitch, first, last)):
                top = module["height"] - t - last["mm"]
                heights, at = [], t + first["mm"]
                while at <= top + 1e-9:
                    heights.append(_num(at))
                    at += pitch["mm"]
                if heights:
                    listed = [_num(h) for h in heights]
                    positions += [
                        {"label": f"hole {i + 1}", "position": {"mm": h}, "from": "bottom end"}
                        for i, h in enumerate(listed)
                    ]
                    shown = listed if len(listed) <= 4 else [*listed[:2], "…", listed[-1]]
                    clauses.append("holes at " + ", ".join(h if h == "…" else _n(h) for h in shown) + " mm")
                    if all(columns.values()):
                        holes = 2 * 2 * len(heights)
                else:
                    problem = "no hole fits between the first and last hole heights"
            else:
                words = (
                    f"first hole {_say(first)} above the bottom shelf face, then every {_say(pitch)}, "
                    f"last hole at least {_say(last)} below the top"
                )
                for found, clause_list in ((positions, clauses), (divider_base, divider_clauses)):
                    found.append({"label": "holes", "position": {"rule": words}, "from": "bottom end"})
                    clause_list.append(f"holes: {words}")
        for name in ("hole diameter", "hole depth", "pins per shelf"):
            form = by_name[name]["form"]
            if form is not None:
                said = f"{name} {_say(form)}" if name != "hole diameter" else f"hole Ø {_say(form)}"
                clauses.append(said)
                divider_clauses.append(said)
        hole_rows = [p for p in positions if p["label"].startswith("hole ")]
        column_rows = [p for p in positions if "column" in p["label"]]
        other_rows = [p for p in positions if p not in hole_rows and p not in column_rows]
        for part, segment, fold in side_parts:
            board_columns = column_rows
            if fold is not None and fold.along == "depth":
                if segment == "front":
                    board_columns = [p for p in column_rows if p["label"].startswith("front")]
                elif segment == "back":
                    board_columns = [p for p in column_rows if p["label"].startswith("rear")]
            listed_heights = [p["position"]["mm"] for p in hole_rows]
            remapped = _holes_on_segment(listed_heights, fold, segment)
            origin = "board's lower end" if segment == "upper" else "bottom end"
            board_holes = [
                {"label": f"hole {i + 1}", "position": {"mm": _num(h)}, "from": origin}
                for i, h in enumerate(remapped)
            ]
            board_positions = board_columns + other_rows + board_holes
            board_clauses = list(clauses)
            if segment == "upper":
                board_clauses.append("heights along the slope from the board's lower end")
            face = "both sides, inner face" if part.endswith("-side") and segment == "" else "inner face"
            cols = 2 if fold is None or fold.along != "depth" else 1
            board_count: int | None
            if holes is None:
                board_count = None
            elif not listed_heights:
                board_count = holes
            else:
                board_count = cols * len(remapped)
                if part.endswith("-side") and segment == "":
                    board_count = 2 * 2 * len(listed_heights)
            entries.append(_entry(
                "shelf_pins", part, what, positions=board_positions, values=list(by_name.values()),
                missing=missing, problem=problem, counts={"shelf_pin_holes": board_count},
                clauses=[face] + board_clauses, source_name=f"{key} data sheet",
            ))
        exact = bool(pitch and first and last and all("mm" in f for f in (pitch, first, last)))
        for part, count, bottom, top in targets:
            divider_positions, row_clauses = list(divider_base), list(divider_clauses)
            row_problem, row_holes = problem, None
            if exact:
                listed, at = [], first["mm"]
                while at <= top - bottom - last["mm"] + 1e-9:
                    listed.append(_num(at))
                    at += pitch["mm"]
                if listed:
                    divider_positions += [
                        {"label": f"hole {i + 1}", "position": {"mm": h}, "from": "bottom end"}
                        for i, h in enumerate(listed)
                    ]
                    shown = listed if len(listed) <= 4 else [*listed[:2], "…", listed[-1]]
                    row_clauses.insert(
                        holes_clause_at, "holes at " + ", ".join(h if h == "…" else _n(h) for h in shown) + " mm"
                    )
                    if all(columns.values()):
                        row_holes = 2 * 2 * len(listed) * count
                else:
                    row_problem = "no hole fits between the first and last hole heights"
            entries.append(_entry(
                "shelf_pins", part, what, positions=divider_positions, values=list(by_name.values()),
                missing=list(missing), problem=row_problem, counts={"shelf_pin_holes": row_holes},
                clauses=[f"each of {count} dividers, both faces"] + row_clauses,
                source_name=f"{key} data sheet",
            ))
    return entries


def _pin_divider_rows(module: Mapping[str, Any], spec: Mapping[str, Any], t: int) -> list[tuple[str, int, float, float]]:
    """(row id, dividers, bottom, top) for each divider row whose span holds an adjustable shelf."""
    if not module.get("dividers"):
        return []
    if not uses_divider_layout(module):
        return [(f"{module['id']}-divider", module["dividers"], float(t), float(module["height"] - t))]
    _t, b = _carcass_tb(module, spec["materials"])
    adjustable = kind_centres(module, t, "adjustable")
    found = []
    for row_id, _length, places in divider_rows(module, t, b):
        holding = [p for p in places if any(p.bottom < centre < p.top for centre in adjustable)]
        if holding:
            found.append((row_id, len(places), holding[0].bottom, holding[0].top))
    return found


# Hinges.


def _cup_centre(edge: Form | None, diameter: Form | None) -> Form | None:
    if edge is None or diameter is None:
        return None
    if "mm" in diameter:
        return _shift(edge, diameter["mm"] / 2)
    return {"rule": f"cup edge distance {_say(edge)} plus half the cup Ø {_say(diameter)}"}


def _door_height(leaf: Mapping[str, Any]) -> float:
    if leaf.get("rectangular", True) and "net" not in leaf:
        return leaf["h"]
    return math.floor(leaf["h"])


def _map_plate_board(
    module: Mapping[str, Any], spec: Mapping[str, Any], side: str, z: float
) -> tuple[str, bool, SideFold | None]:
    mid = module["id"]
    if not module.get("side_folds"):
        return f"{mid}-side", False, None
    t, b = _carcass_tb(module, spec["materials"])
    profile = fold_profile(module, t, b)
    fold = profile.fold_on(side)
    if fold is None:
        return f"{mid}-side-{side}", False, None
    if fold.along == "height":
        if z < fold.from_mm:
            return f"{mid}-side-{side}-lower", False, fold
        return f"{mid}-side-{side}-upper", True, fold
    return f"{mid}-side-{side}-front", False, fold


def _slope_form(form: Form, fold: SideFold, z_abs: float) -> Form:
    if "mm" in form:
        return {"mm": slope_mm(z_abs - fold.from_mm, fold.angle_deg)}
    if "min_mm" in form:
        return {
            "min_mm": slope_mm(form["min_mm"] - fold.from_mm, fold.angle_deg),
            "max_mm": slope_mm(form["max_mm"] - fold.from_mm, fold.angle_deg),
        }
    return form


def _hinge_entries(spec: Mapping[str, Any], inputs: Mapping[str, Any]) -> list[DrillEntry]:
    entries = []
    for module in spec["modules"]:
        t, b = _carcass_tb(module, spec["materials"])
        rects = front_layout(module, t, b)
        for index, front in enumerate(module["fronts"]):
            if front["type"] != "door":
                continue
            leaves = [rect for rect in rects if rect["entry"] == index]
            key = front.get("hinge") or HINGE_ID
            prefix = f"{module['id']}-door-{index + 1}"
            sheet = _sheet(inputs, key)
            groups = _group_leaves(prefix, leaves)
            for part_id, group in groups:
                first = group[0]
                doors = len(group)
                height = _door_height(first)
                per_door, _ = _hinge_count(sheet, int(height))
                borings = {"hinge_cup_borings": per_door * doors}
                what = "hinges"
                if sheet is None:
                    entries.append(_entry(
                        "hinges", part_id, what, positions=[], values=[], missing=_no_sheet(key),
                        counts=borings, clauses=[], source_name=f"{key}: no data sheet",
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
                    if 2 * _shortest(end) >= height:
                        problem = "door too short for the hinge end distance"
                    else:
                        positions = _along(height, per_door, end, origins)
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
                if len(leaves) > 1:
                    clauses.append("hinge edge is the outer edge of each door")
                entries.append(_entry(
                    "hinges", part_id, what, positions=positions, values=list(by_name.values()),
                    missing=missing, problem=problem, counts=borings, clauses=clauses,
                    source_name=f"{key} data sheet",
                ))
                sides = []
                for leaf in group:
                    pos = leaves.index(leaf)
                    if len(leaves) == 1 or pos == 0:
                        sides.append("left")
                    else:
                        sides.append("right")
                entries.extend(
                    _plate_entries(module, spec, part_id, group, sides, per_door, end, sheet, key)
                )
    return entries


def _plate_entries(
    module: Mapping[str, Any], spec: Mapping[str, Any], door_part: str, doors: list[Mapping[str, Any]],
    sides: list[str], per_door: int, end: Form | None, sheet: Mapping[str, Any], key: str,
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
    by_board: dict[str, list[dict[str, Any]]] = {}
    sloped_boards: set[str] = set()
    problem = None
    first = doors[0]
    height = _door_height(first)
    if end is not None and 2 * _shortest(end) < height:
        pairs = list(zip(doors, sides))
        if not module.get("side_folds"):
            pairs = pairs[:1]
        for door, side in pairs:
            z = door["z"]
            door_h = _door_height(door)
            hinges = _along(door_h, per_door, end, ("bottom", "top"))
            for hinge in hinges:
                at = hinge["position"]
                if "rule" in at:
                    level: Form = {"rule": "level with its hinge"}
                    z_abs = z + door_h / 2
                elif hinge["from"] == "top":
                    level = {
                        "min_mm": _num(z + door_h - at["max_mm"]),
                        "max_mm": _num(z + door_h - at["min_mm"]),
                    }
                    z_abs = z + door_h - _shortest(at)
                else:
                    level = _shift(at, z)
                    z_abs = z + (_shortest(at) if "mm" in at or "min_mm" in at else 0)
                part, sloped, fold = _map_plate_board(module, spec, side, z_abs)
                origin = "side's bottom end"
                if sloped and fold is not None and "rule" not in level:
                    level = _slope_form(level, fold, z_abs)
                    origin = "board's lower end"
                    sloped_boards.add(part)
                elif sloped:
                    sloped_boards.add(part)
                by_board.setdefault(part, []).append(
                    {"label": f"plate {hinge['label']}", "position": level, "from": origin}
                )
    elif end is not None:
        problem = "door too short for the hinge end distance"
    setback = by_name["plate setback"]["form"]
    spacing = by_name["plate hole spacing"]["form"]
    extra = []
    if setback is not None:
        extra.append(f"{_say(setback)} from the front edge")
    if spacing is not None:
        extra.append(f"holes {_say(spacing)} apart")
    if not by_board:
        return [_entry(
            "hinges", f"{module['id']}-side", f"mounting plates for {door_part}", positions=[],
            values=list(by_name.values()), missing=missing, problem=problem, counts={},
            clauses=["at the door's hinge edge"] + extra, source_name=f"{key} data sheet",
        )]
    out = []
    for part, positions in by_board.items():
        clauses = ["at the door's hinge edge"]
        if positions:
            clauses.append("plates at " + "; ".join(f"{p['label']} {_say(p['position'])}" for p in positions))
        clauses.extend(extra)
        if part in sloped_boards:
            clauses.append("on the sloped board")
        out.append(_entry(
            "hinges", part, f"mounting plates for {door_part}", positions=positions,
            values=list(by_name.values()), missing=missing, problem=problem, counts={},
            clauses=clauses, source_name=f"{key} data sheet",
        ))
    return out


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
    if inputs is not None:
        check_adjustable_shelf_depths(spec, inputs)
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
        t, b = _carcass_tb(module, spec["materials"])
        for rect in front_layout(module, t, b):
            emitted = {k: v for k, v in rect.items() if k not in {"net", "rectangular"}}
            fronts.append(
                {**emitted, "module": module["id"], "x": module["x"] + rect["x"], "z": module["z"] + rect["z"]}
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
