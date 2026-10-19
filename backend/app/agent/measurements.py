"""The owner's requested measurements, checked by code before a revision is confirmed.

`revise_package` takes, beside its changes, a list of the owner's requested lengths:
the owner's words quoted, the module id (or `envelope`, a wall-shelf id, or `none`
for a length that is not about the piece), the field and the target in millimetres.
`check` holds each entry against what the owner actually wrote since the piece's last
created version and against the revised document, and every length with a unit the
owner wrote must be covered by an entry (design-agents, app-check-2026-10-09). Pure:
it reads no database and calls no model.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.prompts import neutralise
from app.blender.custom_build.derive import DeriveError, overall

UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
GROWS = frozenset({"wider", "taller", "deeper", "more"})
SHRINKS = frozenset({"narrower", "shorter", "less"})
NOT_THE_PIECE = "none"
# The tools whose result "Created <package> version <n>" starts a new revision window.
VERSION_TOOLS = frozenset(
    {"create_piece", "revise_package", "rebuild_piece", "import_design", "import_design_version"}
)

_LENGTH = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?(mm|cm|m)\b", re.IGNORECASE)
_WORD = re.compile(r"[a-zäöüß]+")
_ENVELOPE = {"width": "w", "height": "h", "depth": "d"}
# Module length fields a module may leave unset, and those that hold a list of positions
# (shelf-spacing-and-dividers): an absolute length sets one, and a list holds the value.
LIST_FIELDS = frozenset({"shelf_positions_mm", "divider_positions_mm", "side_folds", "shelf_depths_mm"})
OPTIONAL_FIELDS = LIST_FIELDS | {"shelf_spacing_mm"}
# A quote that asks for a side fold names it with one of these (auto-fit-protruding-shelves).
FOLD_WORDS = ("fold", "bend", "bent", "angle", "slant", "knick", "winkel", "schräg", "°")


@dataclass(frozen=True)
class Length:
    """A length with a unit as the owner wrote it."""

    text: str
    mm: float
    relative: bool = False
    # +1 grows, -1 shrinks, 0 either way ("by 5 cm" with no comparative); 0 when absolute.
    sign: int = 0

    @property
    def key(self) -> tuple[float, bool, int]:
        return (self.mm, self.relative, self.sign)


@dataclass(frozen=True)
class Requested:
    quote: str
    target: str
    field: str
    value_mm: float


def lengths(text: str) -> list[Length]:
    """Every length with a unit (mm, cm, m; comma or dot decimals) in `text`, in millimetres.

    A length followed by "wider", "taller", "deeper" or "more" grows a value; by "narrower",
    "shorter" or "less" shrinks it. A length after "by" is relative too, in the direction
    of a comparative just before it, or either way when there is none.
    """
    found = []
    for match in _LENGTH.finditer(text):
        number, unit = match.groups()
        mm = round(float(number.replace(",", ".")) * UNIT_MM[unit.lower()], 3)
        after = _WORD.findall(text[match.end():].lower())[:1]
        before = _WORD.findall(text[:match.start()].lower())[-4:]
        relative, sign = False, 0
        if after and after[0] in GROWS | SHRINKS:
            relative, sign = True, 1 if after[0] in GROWS else -1
        elif before and before[-1] == "by":
            relative = True
            comparative = [word for word in before[:-1] if word in GROWS | SHRINKS]
            if comparative:
                sign = 1 if comparative[-1] in GROWS else -1
        found.append(Length(text=match.group(0), mm=mm, relative=relative, sign=sign))
    return found


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def field_value(document: Mapping[str, Any], target: str, field: str) -> float | None:
    """A length field of a module, of the envelope, or of a wall shelf; `None` if there is none."""
    if target == "envelope":
        if field not in _ENVELOPE:
            return None
        try:
            return _number(overall(document)[_ENVELOPE[field]])
        except (DeriveError, KeyError, TypeError):
            return None
    for key in ("modules", "wall_shelves"):
        for entry in document.get(key) or []:
            if entry.get("id") == target:
                return _number(entry.get(field))
    return None


def _module(document: Mapping[str, Any], target: str) -> Mapping[str, Any] | None:
    return next((entry for entry in document.get("modules") or [] if entry.get("id") == target), None)


def _holds(document: Mapping[str, Any], target: str, field: str, value: float) -> tuple[bool, str]:
    """Whether the document's field holds `value` (a list field: among its values), and what it holds."""
    if field in LIST_FIELDS:
        module = _module(document, target)
        listed = []
        for item in (module or {}).get(field) or []:
            if isinstance(item, dict):
                found = _number(item.get("from_mm"))
                if found is not None:
                    listed.append(found)
            elif _number(item) is not None:
                listed.append(float(item))
        shown = f"[{', '.join(_mm(float(v)) for v in listed)}]" if listed else "nothing"
        return any(abs(v - value) < 0.5 for v in listed), shown
    after = field_value(document, target, field)
    return after is not None and abs(after - value) < 0.5, "nothing" if after is None else _mm(after)


def _candidates(length: Length, before: float) -> list[float]:
    if not length.relative:
        return [length.mm]
    if length.sign:
        return [before + length.sign * length.mm]
    return [before + length.mm, before - length.mm]


def _mm(value: float) -> str:
    return f"{value:g} mm"


def check(
    requested: Sequence[Requested],
    owner_texts: Sequence[str],
    current: Mapping[str, Any],
    revised: Mapping[str, Any],
) -> list[str]:
    """Each reason the requested measurements do not hold; empty when they all do.

    An entry's quote must be in the owner's texts and give a length with a unit; that
    length (absolute, or relative to the field in `current`) must be the entry's value,
    and `revised` must hold that value. Every length in the owner's texts must be
    covered by an entry; one with target `none` covers the lengths of its quote.
    """
    said = _norm("\n".join(owner_texts))
    covered: set[tuple[float, bool, int]] = set()
    refusals = []
    for entry in requested:
        quote = entry.quote.strip()
        if not quote or _norm(quote) not in said:
            refusals.append(
                f"{quote!r} is not in the owner's messages since the piece's last version; quote the owner's own words"
                + _owner_sentence(lengths(quote), owner_texts)
            )
            continue
        found = lengths(quote)
        if not found and entry.field == "side_folds":
            continue  # a fold asked for by angle or by name alone is held by `fold_refusals`
        if not found:
            refusals.append(f"{quote!r} gives no length with a unit (mm, cm or m)")
            continue
        if entry.target.strip().lower() == NOT_THE_PIECE:
            covered.update(length.key for length in found)
            continue
        before = field_value(current, entry.target, entry.field)
        if before is None or entry.field in LIST_FIELDS:
            if entry.field not in OPTIONAL_FIELDS or _module(current, entry.target) is None:
                refusals.append(f"{entry.target} has no length field {entry.field!r} to set from {quote!r}")
                continue
            absolute = [length for length in found if not length.relative]
            if not absolute:
                refusals.append(
                    f"{quote!r} is relative, but {entry.target} {entry.field} is not set in the latest version; "
                    "state an absolute value"
                )
                continue
            matched = next((length for length in absolute if abs(length.mm - entry.value_mm) < 0.5), None)
            if matched is None:
                refusals.append(
                    f"{quote!r} gives {entry.target} {entry.field} {_mm(absolute[0].mm)}, not {_mm(entry.value_mm)}"
                )
                continue
            covered.add(matched.key)
            held, shown = _holds(revised, entry.target, entry.field, entry.value_mm)
            if not held:
                refusals.append(
                    f"{quote!r} asks for {entry.target} {entry.field} {_mm(entry.value_mm)} expected, "
                    f"but the changes set {shown}"
                )
            continue
        matched = next(
            (length for length in found if any(abs(v - entry.value_mm) < 0.5 for v in _candidates(length, before))),
            None,
        )
        if matched is None:
            expected = " or ".join(_mm(v) for v in _candidates(found[0], before))
            refusals.append(
                f"{quote!r} gives {entry.target} {entry.field} {expected}, not {_mm(entry.value_mm)}"
            )
            continue
        covered.add(matched.key)
        after = field_value(revised, entry.target, entry.field)
        if after is None or abs(after - entry.value_mm) >= 0.5:
            now = "nothing" if after is None else _mm(after)
            refusals.append(
                f"{quote!r} asks for {entry.target} {entry.field} {_mm(entry.value_mm)} expected, "
                f"but the changes set {now}"
            )
    seen: set[tuple[float, bool, int]] = set()
    for text in owner_texts:
        for length in lengths(text):
            if length.key in covered or length.key in seen:
                continue
            seen.add(length.key)
            refusals.append(
                f"the owner's {length.text!r} is not covered: add it to `requested` "
                "(target `none` when it is not about the piece)"
                + _owner_sentence([length], owner_texts)
            )
    return refusals


SENTENCE_CHARS = 200
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _owner_sentence(found: Sequence[Length], owner_texts: Sequence[str]) -> str:
    """The owner's sentence holding one of `found`, as a refusal's tail (conversation-continuity),
    so the Designer can quote it exactly; empty when none does."""
    keys = {length.key for length in found}
    for text in owner_texts:
        for sentence in _SENTENCE_END.split(text):
            sentence = sentence.strip()
            if sentence and any(length.key in keys for length in lengths(sentence)):
                shown = sentence if len(sentence) <= SENTENCE_CHARS else sentence[:SENTENCE_CHARS] + "…"
                return f"; the owner wrote: {neutralise(shown)!r}"
    return ""


def _names_fold(quote: str) -> bool:
    text = quote.casefold()
    return any(word in text for word in FOLD_WORDS)


def fold_refusals(
    requested: Sequence[Requested],
    owner_texts: Sequence[str],
    current: Mapping[str, Any],
    revised: Mapping[str, Any],
) -> list[str]:
    """Each module whose side folds the revision sets, changes or clears without the owner asking.

    A fold changes only with a `requested` entry for that module and field `side_folds` whose
    quote is in the owner's texts and names a fold; a module the revision adds or removes is not
    a fold change. Empty when every fold change was asked for.
    """
    said = _norm("\n".join(owner_texts))
    asked = {
        entry.target.strip()
        for entry in requested
        if entry.field == "side_folds" and entry.quote.strip() and _norm(entry.quote) in said and _names_fold(entry.quote)
    }
    before = {module.get("id"): module.get("side_folds") or [] for module in current.get("modules") or []}
    refusals = []
    for module in revised.get("modules") or []:
        slug = module.get("id")
        if slug not in before or (module.get("side_folds") or []) == before[slug] or slug in asked:
            continue
        refusals.append(
            f"{slug}: the changes would set side_folds, which the owner did not ask for. Keep the fold as it is "
            "and never change it to satisfy another rule; ask the owner instead. When the owner asked, add a "
            "`requested` entry for this module with field `side_folds` quoting the owner's words about the fold"
        )
    return refusals


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def owner_texts_since_version(messages: Iterable[Any], package_id: str) -> list[str]:
    """The owner's message texts and question-form answers after the last result that created a
    version of `package_id`.

    The whole thread when no version of it was created here.
    """
    history = list(messages)
    names = {
        call.get("id"): call.get("name")
        for message in history
        if isinstance(message, AIMessage)
        for call in message.tool_calls or []
    }
    start = 0
    for index, message in enumerate(history):
        if (
            isinstance(message, ToolMessage)
            and names.get(message.tool_call_id) in VERSION_TOOLS
            and _text(message.content).startswith(f"Created {package_id} version ")
        ):
            start = index + 1
    return owner_texts(history[start:])


def owner_texts(messages: Iterable[Any]) -> list[str]:
    """The owner's message texts and question-form answers in `messages`, in order."""
    texts = []
    for message in messages:
        if isinstance(message, HumanMessage):
            texts.append(_text(message.content))
        elif isinstance(message, ToolMessage):
            texts.extend(_form_answers(message))
    return texts


def _form_answers(message: ToolMessage) -> list[str]:
    """The owner's answers to a question form, as the tool node recorded them by code: each
    answer given, or the text written instead; never a question's text (conversation-continuity)."""
    answered = message.additional_kwargs.get("answers")
    if not isinstance(answered, Mapping):
        return []
    declined = answered.get("declined")
    if isinstance(declined, str) and declined.strip():
        return [declined.strip()]
    rows = answered.get("rows") or []
    return [str(row["answer"]) for row in rows if isinstance(row, Mapping) and str(row.get("answer") or "").strip()]
