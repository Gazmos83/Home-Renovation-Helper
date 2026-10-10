"""Questions a new divider raises before a version is proposed (partial-and-folded-dividers).

`create_piece` and `revise_package` answer with one of these instead of a
confirmation, so the Designer has to ask the owner:

- `fix_shelf_question`: a divider names an adjustable shelf; only a fixed shelf
  can hold one, so the owner is asked whether to fix it, with the hardware it
  changes worked out by deriving both versions.
- `position_question`: a new divider has no position; the owner is given the
  centred position, the compartment widths, and the configured shelf-span limit
  with its source, or the plain statement that none is configured.

Pure: no database, no model.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from app.blender.custom_build import derive as custom_derive
from app.blender.custom_build.derive import DeriveError
from app.blender.schemas import CustomBuildSpec
from app.blender.spec_contract import SpecValidationError

SHELF_SPAN_CHECK = "shelf_span_mm_for_thickness"


def _modules_by_id(document: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    return {module["id"]: module for module in (document or {}).get("modules") or []}


def _thickness(document: Mapping[str, Any], module: Mapping[str, Any]) -> tuple[int, int]:
    materials = document["materials"]
    t = materials[module["carcass"]]["thickness_mm"]
    b = materials[module["back"]]["thickness_mm"] if module.get("back") is not None else 0
    return t, b


def _hardware_qty(document: Mapping[str, Any], module_id: str) -> dict[str, tuple[str, Any]]:
    """The hardware of the document with that module's dividers left out, validated like any document."""
    plain = copy.deepcopy(dict(document))
    for module in plain["modules"]:
        if module["id"] == module_id:
            for field in ("dividers", "divider_positions_mm", "divider_spans"):
                module.pop(field, None)
    spec = CustomBuildSpec.model_validate(plain).model_dump(mode="json")
    _parts, hardware, _assembly = custom_derive.derive(spec)
    return {line["id"]: (line["item"], line["qty"]) for line in hardware}


def fix_shelf_question(document: Mapping[str, Any]) -> str | None:
    """The question to ask when a divider stands on or reaches an adjustable shelf, or `None`.

    Runs before validation; a document too malformed to read gives `None`, and validation names the problem.
    """
    try:
        return _fix_shelf_question(document)
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration):
        return None


def _fix_shelf_question(document: Mapping[str, Any]) -> str | None:
    for module in document.get("modules") or []:
        spans = module.get("divider_spans") or []
        kinds = custom_derive.shelf_kinds_of(module)
        named = sorted(
            {
                board
                for span in spans
                for board in (span.get("from_board"), span.get("to_board"))
                if isinstance(board, int) and 1 <= board <= len(kinds) and kinds[board - 1] == "adjustable"
            }
        )
        if not named:
            continue
        fixed = copy.deepcopy(dict(document))
        target = next(m for m in fixed["modules"] if m["id"] == module["id"])
        new_kinds = list(kinds)
        for number in named:
            new_kinds[number - 1] = "fixed"
        target["shelf_kinds"] = new_kinds
        target["shelves"] = new_kinds.count("fixed")
        target["adjustable_shelves"] = new_kinds.count("adjustable")
        shelves_said = ", ".join(f"shelf {number}" for number in named)
        effect = _hardware_effect(document, fixed, module["id"])
        return (
            f"No version proposed: in module {module['id']!r} the divider names {shelves_said}, which is "
            "adjustable. Only a fixed shelf can hold a divider. Tell the owner that, and ask whether to fix "
            f"{shelves_said}. Fixing changes: {effect}. If the owner says yes, revise `shelves` "
            f"{target['shelves']}, `adjustable_shelves` {target['adjustable_shelves']} and `shelf_kinds` "
            f"{new_kinds} together with the divider. If the owner says no, do not add the divider and say why. "
            "Never change a shelf's kind without the owner's yes."
        )
    return None


def _hardware_effect(before: Mapping[str, Any], after: Mapping[str, Any], module_id: str) -> str:
    try:
        was, now = _hardware_qty(before, module_id), _hardware_qty(after, module_id)
    except (DeriveError, SpecValidationError, KeyError, IndexError, TypeError, ValueError):
        return "the shelf becomes a fixed board screwed with 4 confirmat screws, and it needs no shelf pins"
    said = []
    for key in dict.fromkeys([*was, *now]):
        item, old = was.get(key, (now.get(key, ("", 0))[0], 0))
        _item, new = now.get(key, (item, 0))
        if old == new:
            continue
        if old == "" or new == "":
            said.append(f"{item}: no quantity (its data sheet lacks the pins per shelf), one shelf fewer")
        else:
            said.append(f"{item} {old} → {new}")
    return "; ".join(said) or "no hardware line changes"


def _new_unpositioned(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Modules whose dividers are new (count rose, or spans added or changed) and have no positions."""
    previous = _modules_by_id(before)
    found = []
    for module in after.get("modules") or []:
        if not module.get("dividers") or module.get("divider_positions_mm"):
            continue
        old = previous.get(module["id"])
        if (
            old is None
            or module["dividers"] > (old.get("dividers") or 0)
            or (module.get("divider_spans") and module.get("divider_spans") != old.get("divider_spans"))
        ):
            found.append(module)
    return found


def _span_rule(rules: Sequence[Any], t: int) -> tuple[float, Any] | None:
    """The shelf-span limit for a board of `t` mm and the rule's source, or `None` when none applies."""
    for rule in rules:
        if rule.check != SHELF_SPAN_CHECK:
            continue
        entries = sorted(rule.params.table, key=lambda entry: entry.thickness_mm)
        fitting = [entry for entry in entries if entry.thickness_mm <= t]
        if fitting:
            return fitting[-1].max_span_mm, rule.source
    return None


def _compartments(module: Mapping[str, Any], t: int, b: int) -> list[str]:
    """The compartment widths the dividers make, at each split shelf, or across the span when none is split."""
    boards = custom_derive.shelf_boards(module, t, b)
    split: dict[int, list[int]] = {}
    for board in boards:
        if board.bay is not None:
            split.setdefault(board.level, []).append(board.width)
    if split:
        return [
            f"at shelf {level}: " + " and ".join(f"{width} mm" for width in widths)
            for level, widths in split.items()
        ]
    places = custom_derive.divider_places(module, t, b)
    low = min(place.bottom for place in places)
    high = max(place.top for place in places)
    if module.get("side_folds"):
        left, opening = custom_derive.narrowest_opening(custom_derive.fold_profile(module, t, b), low, high)
        right = left + opening
        where = "at the narrowest part of the span"
    else:
        left, right = t, module["width"] - t
        where = "across the span"
    edges: list[float] = [left]
    for place in sorted(places, key=lambda p: p.left):
        edges += [place.left, place.left + t]
    edges.append(right)
    widths = [int(end - start) for start, end in zip(edges[::2], edges[1::2], strict=True)]
    return [f"{where}: " + " and ".join(f"{width} mm" for width in widths)]


def position_question(
    before: Mapping[str, Any] | None, after: Mapping[str, Any], rules: Sequence[Any]
) -> str | None:
    """The question to ask when a new divider has no position, or `None` when every new divider has one."""
    modules = _new_unpositioned(before, after)
    if not modules:
        return None
    lines = [
        (
            "No version proposed: a new divider needs its position. Ask the owner, give this recommendation, "
            "and wait for the answer:"
        )
    ]
    for module in modules:
        t, b = _thickness(after, module)
        places = custom_derive.divider_places(module, t, b)
        positions = [int(place.left - t) for place in places]
        noun = "divider" if len(places) == 1 else "dividers"
        centred = "centred" if len(places) == 1 else "equal compartments"
        if module.get("side_folds"):
            centred += " in the narrowest part of the folded opening"
        lines.append(
            f"- module {module['id']!r}: {len(places)} {noun} at {positions} mm from the left side's inner face "
            f"({centred}); compartments " + "; ".join(_compartments(module, t, b)) + "."
        )
        limit = _span_rule(rules, t)
        if limit is None:
            lines.append(
                f"  No shelf-span limit is configured for {t} mm boards, so the compartment widths are not "
                "checked against one; say so."
            )
        else:
            span, source = limit
            widest = custom_derive.widest_shelf_board(module, t, b)
            within = widest is None or widest.width <= span
            verdict = "every compartment is within it" if within else f"the widest board, {widest.width} mm, exceeds it"
            lines.append(
                f"  Shelf-span limit for {t} mm boards: at most {span:g} mm ({source.publication}, {source.section}: "
                f'"{source.quote}"); {verdict}.'
            )
    lines.append(
        "Also call search_guidelines for shelf-span or divider passages and cite any that apply. When the owner "
        "accepts, send `divider_positions_mm` with the recommended values; when the owner gives a position, "
        "send that."
    )
    return "\n".join(lines)
