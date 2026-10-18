"""Correcting an imported design's hand-written hardware against the rules in force (hardware-catalog).

An import comes from another chat, whose hardware list is often wrong: it repeats what the app's
rules already count (hinges, shelf pins, runners, connectors, handles, brackets) or lists knobs that
a front's `handle` would draw. Code, never a model, checks each hand-written line against the
hardware the rules derive for the same design and the hardware catalog:

- a line whose id equals a rule-counted line is removed, and the rule's count stands;
- a line whose item text matches a catalog entry of a rule-counted kind is removed when the design
  derives a line of that kind, and otherwise kept with a warning that nothing in the design uses it;
- a knob, pull or handle line while no front carries a `handle` is kept, with a warning saying how
  to write it as a modelled `handle`;
- anything else is kept as written.

The corrected design is what the owner confirms and what is stored.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.blender.custom_build import derive
from app.blender.hardware_catalog import Catalog, CatalogEntry

_FINISH_WORDS = ("black", "aluminium", "steel", "brass", "nickel", "chrome")


@dataclass
class Corrections:
    design: dict[str, Any]
    removals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [f"Removed {text}" for text in self.removals] + self.warnings


def _kind(entry: CatalogEntry) -> str:
    """What makes two items the same: the shape, except that bars and knobs also stand for
    never-drawn items (screws, stays, latches), so those are told apart by their entry."""
    return entry.name if entry.shape in ("bar", "knob") else entry.shape


def _is_handle(entry: CatalogEntry) -> bool:
    return entry.name.startswith("handle-")


def _free_lists(design: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
    for module in design.get("modules") or []:
        yield module.setdefault("hardware", [])
    for part in design.get("extra_parts") or []:
        yield part.setdefault("hardware", [])
    yield design.setdefault("hardware", [])


def rule_lines(design: Mapping[str, Any], inputs: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The hardware the rules derive for `design` with every hand-written line left out."""
    stripped = copy.deepcopy(dict(design))
    for lines in _free_lists(stripped):
        lines.clear()
    _parts, hardware, _assembly = derive.derive(stripped, inputs)
    return hardware


def _matched(catalog: Catalog, item: str) -> CatalogEntry | None:
    """The entry whose longest `matches` phrase the item text contains."""
    text = item.casefold()
    best: tuple[int, CatalogEntry] | None = None
    for entry in catalog.entries:
        for phrase in entry.matches:
            if phrase in text and (best is None or len(phrase) > best[0]):
                best = (len(phrase), entry)
    return best[1] if best else None


def _quantity(qty: Any) -> str:
    return f"×{qty}" if qty != "" else "(no quantity)"


def correct(design: Mapping[str, Any], derived: list[Mapping[str, Any]], catalog: Catalog) -> Corrections:
    """A copy of `design` with its hand-written hardware corrected against `derived` (the rule lines)."""
    corrected = copy.deepcopy(dict(design))
    result = Corrections(corrected)
    by_id = {line["id"]: line for line in derived}
    by_kind: dict[str, Mapping[str, Any]] = {}
    for line in derived:
        entry = catalog.entry_for(line["id"])
        if entry is not None and entry.rule_counted:
            by_kind.setdefault(_kind(entry), line)
    handles_drawn = any(entry is not None and _is_handle(entry) for entry in map(catalog.entry_for, by_id))
    # One line per hand-written id and outcome, its quantities summed over every list it appears in.
    found: dict[tuple[str, str, str], dict[str, Any]] = {}

    def note(outcome: str, line: Mapping[str, Any], reason: str) -> None:
        seen = found.setdefault((outcome, line["id"], reason), {"item": line["item"], "qty": 0, "places": 0})
        seen["qty"] = "" if line["qty"] == "" or seen["qty"] == "" else seen["qty"] + line["qty"]
        seen["places"] += 1

    for lines in _free_lists(corrected):
        kept: list[dict[str, Any]] = []
        for line in lines:
            rule = by_id.get(line["id"])
            if rule is not None:
                note("removed", line, f"the rules already count `{rule['id']}` {_quantity(rule['qty'])}")
                continue
            entry = _matched(catalog, line["item"])
            if entry is None or not entry.rule_counted:
                kept.append(line)
                continue
            same = by_kind.get(_kind(entry))
            if same is not None:
                note("removed", line, f"the rules already count it as `{same['id']}` {_quantity(same['qty'])}")
                continue
            kept.append(line)
            if _is_handle(entry) and not handles_drawn:
                kind = "knob" if entry.shape == "knob" else "bar"
                finish = next((word for word in _FINISH_WORDS if word in line["item"].casefold()), None)
                written = f"kind `{kind}`" + (f" and finish `{finish}`" if finish else "")
                note("kept", line, f"it is not drawn; it can be written as a front's `handle` with {written}")
            elif not _is_handle(entry):
                note("kept", line, "nothing in the design uses it")
        lines[:] = kept
    for (outcome, identifier, reason), seen in found.items():
        where = f" in {seen['places']} places" if seen["places"] > 1 else ""
        text = f"`{identifier}` {seen['item']!r} {_quantity(seen['qty'])}{where}: {reason}"
        if outcome == "removed":
            result.removals.append(text)
        else:
            result.warnings.append(f"Kept {text}")
    return result
