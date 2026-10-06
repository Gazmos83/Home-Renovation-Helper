"""Parsing toom's product-page specification table (design.md decision 1).

Walks the extracted text from the `Eigenschaften` heading to `Datenblätter` or
the page's end. A line that doubles itself (`BreiteBreite`) is a key; the
line after it is that key's value, kept verbatim — normalising units is a
consumer's job, not this parser's, and a place to introduce error. A known
section heading between rows updates the group attributes are recorded under
without itself becoming a key. Nothing outside this region — the description,
the product name — is ever read into an attribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.ingestion.extract import extract_text

EIGENSCHAFTEN_HEADING: Final = "Eigenschaften"
DATENBLAETTER_HEADING: Final = "Datenblätter"

# toom's own section headings, established by the 2026-09-17 probe. Recorded
# as the group of the rows beneath them; never treated as a key themselves.
SECTION_HEADINGS: Final = frozenset(
    {
        "Maße & Gewichte",
        "Produktdetails",
        "Lieferinformationen",
        "Weitere Eigenschaften",
        "Herstellerinformationen",
    }
)


@dataclass(frozen=True, slots=True)
class SpecAttribute:
    key: str
    value: str
    group: str | None


@dataclass(frozen=True, slots=True)
class SpecResult:
    attributes: tuple[SpecAttribute, ...]
    # False when the page carries no `Eigenschaften` heading at all: the
    # caller reports `specs: unreadable` rather than an empty table.
    readable: bool
    # The region's own text, verbatim — what `check_live_listing` wraps as
    # the specification passage the model reads (design.md decision 4).
    # Empty when `readable` is False.
    region_text: str = ""


def _doubled_key(line: str) -> str | None:
    """`line`'s key half, if `line` is exactly that key written twice."""
    if len(line) < 2 or len(line) % 2 != 0:
        return None
    half = len(line) // 2
    first, second = line[:half], line[half:]
    return first if first and first == second else None


def _split_after_heading(line: str, heading: str) -> str | None:
    """The rest of `line` once its `heading` prefix is removed, if it has one.

    The live page fuses the `Eigenschaften` heading directly onto the first
    subsection heading with no line break between them
    (`"EigenschaftenMaße & Gewichte"`), and does the same for `Datenblätter`
    and the datasheet link's own text. A plain `==` match would miss both
    boundaries entirely on the real page, so this matches a prefix and
    returns what follows it — which may itself be meaningful text, not
    something to discard.
    """
    stripped = line.strip()
    if not stripped.startswith(heading):
        return None
    return stripped[len(heading) :].strip()


def parse_specifications(html: str) -> SpecResult:
    lines = extract_text(html).splitlines()

    start = next(
        (i for i, line in enumerate(lines) if _split_after_heading(line, EIGENSCHAFTEN_HEADING) is not None),
        None,
    )
    if start is None:
        return SpecResult(attributes=(), readable=False)

    # Whatever followed "Eigenschaften" on its own line — typically the first
    # subsection heading, fused on with no separator — is the region's own
    # first line, not part of the heading to discard.
    remainder = _split_after_heading(lines[start], EIGENSCHAFTEN_HEADING) or ""
    body = ([remainder] if remainder else []) + lines[start + 1 :]

    end = next(
        (i for i, line in enumerate(body) if _split_after_heading(line, DATENBLAETTER_HEADING) is not None),
        len(body),
    )
    region = [line.strip() for line in body[:end]]

    attributes: list[SpecAttribute] = []
    group: str | None = None
    index = 0
    while index < len(region):
        line = region[index]
        if not line:
            index += 1
            continue
        if line in SECTION_HEADINGS:
            group = line
            index += 1
            continue

        key = _doubled_key(line)
        value = region[index + 1] if index + 1 < len(region) else ""
        if key is not None and value and value not in SECTION_HEADINGS:
            attributes.append(SpecAttribute(key=key, value=value, group=group))
            index += 2
            continue

        # Not a key/value pair this parser trusts: skip rather than guess,
        # so an unexpected line never becomes a fabricated attribute.
        index += 1

    return SpecResult(
        attributes=tuple(attributes), readable=True, region_text="\n".join(region)
    )
