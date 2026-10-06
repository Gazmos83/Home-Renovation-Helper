"""Parsing toom's category-listing markup for price, stock and the product URL.

Design.md decision 1: read by a small set of anchored regexes over one matched
product block, never over the whole page — so a figure from a neighbouring
product can never bleed into this one. The block is located in the raw
markup (its `/p/` link only exists as an href), but every string this returns
is read from the block's own text after it passes through the same
hidden-content-stripping extraction as ingestion (CLAUDE.md §8a item 3).

Grounded in a live fetch of a real category page (2026-09-17, `/c/bauen-
renovieren/baustoffe/daemmung/hartschaumplatten`, CLAUDE.md §10 step 10.1),
which corrected three assumptions an earlier, unverified draft made:

- Each tile is `<a data-testid="m-product-teaser" href="/p/...">`, not a
  bespoke wrapper; the product name lives in a
  `data-testid="m-product-teaser-name"` child, because the tile's own flattened
  text also contains the price and stock line.
- A tile states both a per-unit price ("15,98 € / m²") and the price of the
  purchasable pack ("7,99 € / Pack"), fused with no separator between them.
  The pack price is what `price` reports; the per-unit figure is `unit_price`.
- "No home delivery" is `"Keine Lieferung nach Hause"`, which contains the
  positive phrase as a substring — a plain `in` check reads it backwards.
  Stock is one of three verbs ("Verfügbar", "Nicht verfügbar", "Bestellbar"
  in") followed by the store, with an optional "Nur wenige verfügbar" fused
  onto the store name with no separator when stock is low.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from bs4 import BeautifulSoup

from app.ingestion.extract import extract_text

# The real, stable signal a product tile carries (see module docstring). The
# parser degrades to `unreadable` rather than guessing when it is not there
# (design.md §13) — the live-marked test is what would catch this changing.
_PRODUCT_TILE_TESTID: Final = "m-product-teaser"
_PRODUCT_NAME_TESTID: Final = "m-product-teaser-name"
_PRODUCT_URL = re.compile(r"^/p/[a-z0-9-]+/\d+", re.IGNORECASE)

# The pack price — what a shopper actually pays — is always suffixed "/ Pack"
# on toom's listing; matched first so it is never mistaken for the per-unit
# figure. A page with only a single, unsuffixed price (no per-unit split)
# falls back to that.
_PACK_PRICE = re.compile(r"(\d{1,4},\d{2})\s*€\s*/\s*Pack\b")
_STANDALONE_PRICE = re.compile(r"(\d{1,4},\d{2})\s*€(?!\s*/)")
# The unit word is matched as non-digit characters only: toom's listing fuses
# the pack price directly onto it with no separator ("m²7,99 € / Pack"), and
# a `\S+` here would swallow straight into that following price's digits.
_UNIT_PRICE = re.compile(r"(\d{1,4},\d{2}\s*€\s*/\s*(?!Pack\b)[^\s\d]+)")

IN_STOCK_VERB: Final = "Verfügbar"
OUT_OF_STOCK_VERB: Final = "Nicht verfügbar"
ORDERABLE_VERB: Final = "Bestellbar"
# Longest alternative first: matching "Verfügbar" before "Nicht verfügbar" has
# been tried would only ever match the tail of the negated phrase.
_STOCK = re.compile(r"(Nicht verfügbar|Verfügbar|Bestellbar) in ([^\n]+)")

DELIVERY_TEXT: Final = "Lieferung nach Hause"
NO_DELIVERY_TEXT: Final = "Keine Lieferung nach Hause"
LOW_STOCK_NOTE: Final = "Nur wenige verfügbar"


@dataclass(frozen=True, slots=True)
class ListingBlock:
    """One product tile, as the listing page states it."""

    name: str
    url: str
    price: str | None
    unit_price: str | None
    delivery: bool
    stock_store: str | None
    stock_verb: str | None
    stock_note: str | None
    text: str


def _price_fields(text: str) -> tuple[str | None, str | None]:
    pack_match = _PACK_PRICE.search(text)
    if pack_match:
        price = pack_match.group(1)
    else:
        standalone_match = _STANDALONE_PRICE.search(text)
        price = standalone_match.group(1) if standalone_match else None
    unit_match = _UNIT_PRICE.search(text)
    return price, (unit_match.group(1) if unit_match else None)


def _stock_fields(text: str) -> tuple[str | None, str | None, str | None]:
    match = _STOCK.search(text)
    if match is None:
        return None, None, None
    verb = match.group(1)
    raw_store = match.group(2).strip()
    note = None
    if raw_store.endswith(LOW_STOCK_NOTE):
        raw_store = raw_store[: -len(LOW_STOCK_NOTE)].strip()
        note = LOW_STOCK_NOTE
    return verb, (raw_store or None), note


def parse_listing_blocks(html: str) -> list[ListingBlock]:
    """Every product tile the page carries. Empty means the markup is unreadable."""
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[ListingBlock] = []

    for tile in soup.find_all("a", attrs={"data-testid": _PRODUCT_TILE_TESTID}):
        href = tile.get("href")
        if not href or not _PRODUCT_URL.match(str(href)):
            continue
        name_element = tile.find(attrs={"data-testid": _PRODUCT_NAME_TESTID})
        name = name_element.get_text(" ", strip=True) if name_element is not None else ""
        if not name:
            continue

        text = extract_text(str(tile))
        price, unit_price = _price_fields(text)
        stock_verb, stock_store, stock_note = _stock_fields(text)

        blocks.append(
            ListingBlock(
                name=name,
                url=str(href),
                price=price,
                unit_price=unit_price,
                delivery=DELIVERY_TEXT in text and NO_DELIVERY_TEXT not in text,
                stock_store=stock_store,
                stock_verb=stock_verb,
                stock_note=stock_note,
                text=text,
            )
        )
    return blocks


_PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def _comparable(text: str) -> str:
    """Casefolded, punctuation-free, single-spaced — the form names are matched in.

    toom quotes model codes inside product names ("Mehrzweckdämmplatte 'EPS 040
    DEO dm' 1000 x 500 x 100 mm") and hyphenates compounds
    ("Styrodur-Hartschaumplatte"); day 6's failure pass found that a query
    phrased exactly as toom names the product still failed a raw substring
    test because of those quotes. Punctuation is not part of what a shopper
    means, so it is dropped on both sides before comparing.
    """
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", text.casefold())).strip()


# Tokens that say nothing about which product is meant: units and joiners
# that appear in most names on a page.
_UNIT_TOKENS: Final = frozenset(
    {"mm", "cm", "m", "m2", "m²", "kg", "g", "l", "x", "pack", "stück", "stk", "st"}
)
_HAS_DIGIT = re.compile(r"\d")


def _distinctive_tokens(text: str) -> set[str]:
    """Model codes, sizes and real words — what a shopper uses to name a product."""
    return {
        token
        for token in _comparable(text).split()
        if token not in _UNIT_TOKENS and (_HAS_DIGIT.search(token) or len(token) >= 3)
    }


def _ranked_block(blocks: list[ListingBlock], query: str) -> ListingBlock | None:
    """The unique tile sharing the most distinctive tokens with the query.

    Day 6's failure pass: a shopper says "Hartschaumplatte EPS 040" for what
    toom lists as "Mehrzweckdämmplatte 'EPS 040 DEO dm' …". Containment cannot
    bridge the category word, so tiles are scored by shared codes and words.
    Conservative on purpose (design decision 11): a tie returns nothing, and
    so does a match resting on words alone — "EPS 040" must actually be there.
    """
    wanted = _distinctive_tokens(query)
    if not wanted:
        return None
    scored: list[tuple[int, bool, ListingBlock]] = []
    for block in blocks:
        shared = wanted & _distinctive_tokens(block.name)
        if shared:
            code_like = any(_HAS_DIGIT.search(token) for token in shared)
            scored.append((len(shared), code_like, block))
    if not scored:
        return None
    best = max(score for score, _, _ in scored)
    winners = [(code_like, block) for score, code_like, block in scored if score == best]
    if len(winners) != 1 or not winners[0][0]:
        return None
    return winners[0][1]


def find_block(blocks: list[ListingBlock], query: str) -> ListingBlock | None:
    """The tile the query means, or `None` when that cannot be said honestly.

    Containment first — the first block whose name contains `query`, ignoring
    case and punctuation. Only when no name contains it, the conservative
    token ranking above. The listing page has already been resolved for this
    query (via an explicit URL or the catalog), so this only has to pick the
    block that page is actually about; a query no tile can be matched to
    unambiguously is `None` — "not on this page", never a guess.
    """
    needle = _comparable(query)
    if not needle:
        return None
    contained = next((block for block in blocks if needle in _comparable(block.name)), None)
    if contained is not None:
        return contained
    return _ranked_block(blocks, query)
