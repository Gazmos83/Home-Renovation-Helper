"""HTML to storable text.

CLAUDE.md §4 step 3 and §8a item 3: what reaches the corpus must be what a
visitor can actually read. Scripts, styles, comments and hidden elements are
removed before anything is chunked, because hidden markup is a standard place
to park an injection payload and it would otherwise arrive in the model's
prompt wearing the authority of a retailer's page.

This module is deliberately standalone: day 4's live-lookup tool fetches pages
with no ingestion review step at all, so it must run the identical extraction
rather than a similar one.
"""

from __future__ import annotations

import re
from typing import Final

from bs4 import BeautifulSoup, Comment

# Removed entirely, contents included. `template` and `noscript` hold markup
# that is never rendered as-is; `svg` carries no prose worth keeping.
DROPPED_TAGS: Final = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "head",
    "nav",
    "footer",
)

_HIDDEN_STYLE = re.compile(
    r"(display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE
)

# Only these end a line. Everything else is inline and must join without a
# separator, or a price split across sibling spans — which is how toom renders
# them — arrives as "35 \n , \n 25 \n €" and is useless to retrieve on.
BLOCK_TAGS: Final = (
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li",
    "main", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
)

_WHITESPACE = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


# A container that is mostly links and barely any prose is a menu, not
# content. toom repeats its whole category tree on every page; ingesting it
# would put the same few thousand characters of navigation into every chunk
# and drown the text that actually differs between pages.
NAVIGATION_MIN_LINKS: Final = 2
NAVIGATION_LINK_DENSITY: Final = 0.6
# A product grid is also mostly links, so density alone would delete the
# catalogue along with the menu. Menu entries are short ("Holz", "Fliesen");
# product links carry a full description ("Möbelbauplatte beschichtet 2630 x
# 400 x 19 mm"), so mean link length separates the two cleanly.
NAVIGATION_MAX_MEAN_LINK: Final = 30
# Never delete a container holding a large share of the page: the menu is a
# small part of the document, and a wrapper that happens to enclose it must
# not take the content with it.
NAVIGATION_MAX_PAGE_SHARE: Final = 0.35


def _strip_navigation(soup: BeautifulSoup) -> None:
    document_length = len(soup.get_text(" ", strip=True)) or 1

    # Deepest first, so a menu is removed at its own level rather than by way
    # of some ancestor that also contains real content.
    candidates = soup.find_all(["div", "section", "ul", "aside", "header"])
    for element in sorted(candidates, key=lambda tag: -len(list(tag.parents))):
        if element.decomposed:
            continue
        links = element.find_all("a")
        if len(links) < NAVIGATION_MIN_LINKS:
            continue
        total = len(element.get_text(" ", strip=True))
        if not total or total / document_length > NAVIGATION_MAX_PAGE_SHARE:
            continue
        link_lengths = [len(link.get_text(" ", strip=True)) for link in links]
        linked = sum(link_lengths)
        mean_link = linked / len(link_lengths)
        if (
            linked / total >= NAVIGATION_LINK_DENSITY
            and mean_link <= NAVIGATION_MAX_MEAN_LINK
        ):
            element.decompose()


def _is_hidden(tag) -> bool:
    # `attrs` is None on an element that has already been decomposed — which
    # happens whenever a hidden ancestor was removed before this element was
    # reached. Reading it would raise, so decomposed nodes are simply not
    # hidden: they are already gone.
    attributes = getattr(tag, "attrs", None)
    if not attributes:
        return False
    if "hidden" in attributes:
        return True
    if attributes.get("aria-hidden") == "true":
        return True
    style = attributes.get("style")
    return bool(style and _HIDDEN_STYLE.search(style))


def visible_text(html: str) -> str:
    """The text a visitor can read, with menus left in.

    Navigation is boilerplate in a product page and content in a store page —
    the list of nearby markets *is* what a store page is for. Callers that
    need specific structured facts use this; the corpus uses `extract_text`,
    which strips menus on top.
    """
    return _to_text(html, strip_navigation=False)


def extract_text(html: str) -> str:
    """Return the readable text of `html`, with non-content markup removed.

    Visible text is returned verbatim — including anything that reads like an
    instruction. Rewriting it would be a silent edit to a retailer's content;
    containment is the prompt's job (§8a item 2), not the extractor's.
    """
    return _to_text(html, strip_navigation=True)


def _to_text(html: str, *, strip_navigation: bool) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in DROPPED_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for element in soup.find_all(True):
        if not element.decomposed and _is_hidden(element):
            element.decompose()

    if strip_navigation:
        _strip_navigation(soup)

    # Mark block boundaries explicitly, then join everything else verbatim so
    # inline fragments recombine into the words and figures they render as.
    for element in soup.find_all(BLOCK_TAGS):
        element.append("\n")

    text = soup.get_text("")
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    joined = "\n".join(line for line in lines if line)
    return _BLANK_LINES.sub("\n\n", joined).strip()


def chunk_text(
    text: str, *, max_characters: int = 1200, overlap: int = 120
) -> list[str]:
    """Split text into overlapping chunks on paragraph boundaries where it can.

    Overlap keeps a sentence that straddles a boundary retrievable from either
    side. Paragraphs longer than the limit are split on length rather than
    dropped.
    """
    if not text.strip():
        return []

    paragraphs = [block.strip() for block in text.split("\n") if block.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_characters:
            chunks.append(paragraph[:max_characters])
            paragraph = paragraph[max_characters - overlap :]
        current = paragraph

    if current:
        chunks.append(current)
    return chunks
