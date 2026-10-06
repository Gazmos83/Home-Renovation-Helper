"""What each retail source looks like.

One entry, `toom`. The robots.txt review recorded in the README retired
bauhaus, oki and kaufland; their entries are not kept as commented-out code
because a source that cannot be fetched is not configuration, it is history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import zip_longest
from typing import Final


@dataclass(frozen=True)
class SourceGroup:
    """One reviewed kind of page, and the share of a run's budget it gets.

    Discovery allocates the page budget across groups rather than taking the
    first URLs the sitemaps list, so one large group (toom lists tens of
    thousands of products) cannot crowd out the guides and policies a
    shopper's questions are answered from (retail-ingestion).
    """

    name: str
    patterns: tuple[re.Pattern[str], ...]
    share: float
    # Optional sub-kinds taken in turn within the group, so one numerous kind
    # (toom lists hundreds of screws) cannot use up the group's whole share.
    buckets: tuple[re.Pattern[str], ...] = ()

    def matches(self, url: str) -> bool:
        return any(pattern.search(url) for pattern in self.patterns)

    def diversified(self, urls: list[str]) -> list[str]:
        """`urls` reordered to take one from each bucket in turn."""
        if not self.buckets:
            return urls
        queues: list[list[str]] = [[] for _ in self.buckets]
        rest: list[str] = []
        for url in urls:
            index = next((i for i, bucket in enumerate(self.buckets) if bucket.search(url)), None)
            (rest if index is None else queues[index]).append(url)
        ordered: list[str] = []
        for row in zip_longest(*queues, rest):
            ordered.extend(url for url in row if url)
        return ordered


@dataclass(frozen=True)
class RetailSource:
    """A source's identity, entry points, and what is worth ingesting."""

    name: str
    base_url: str
    sitemap_urls: tuple[str, ...]
    # Only URLs matching one group are considered, and each URL belongs to the
    # first group it matches. Discovery is bounded by the budget too, but the
    # groups keep the budget spent on relevant pages rather than on whatever
    # the sitemap happened to list first.
    groups: tuple[SourceGroup, ...]
    # Assigned to a chunk when no more specific label applies.
    default_category: str = "catalog"

    @property
    def include_patterns(self) -> tuple[re.Pattern[str], ...]:
        return tuple(pattern for group in self.groups for pattern in group.patterns)

    def group_of(self, url: str) -> str | None:
        return next((group.name for group in self.groups if group.matches(url)), None)

    def categorise(self, url: str) -> str:
        if "/hilfe/" in url or "/agb/" in url:
            return "policy"
        if "/service/" in url or "/ratgeber/" in url or "/selbermachen/" in url:
            return "guide"
        if "/p/" in url:
            # Its own category: a cached product page carries published
            # specifications, and the live lookup (which resolves listings from
            # `catalog` pages) must never mistake one for a listing.
            return "product"
        if "/m/" in url:
            return "store"
        return self.default_category


def _patterns(*fragments: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(fragment) for fragment in fragments)


# The product keywords the workshop works with, reviewed 2026-09-23 against
# toom's product sitemaps (`/p/<slug>/<id>` carries no category path, so the
# slug is what can be selected on). Each keyword was checked for precision:
# `multiplex` alone matched bathtub fittings, `siebdruck` screen-printed glass
# doors, `leimholz` terrace roofs and `osb` a carpet named "Crosby", so the
# panel words are used instead.
_PRODUCT_KEYWORDS: Final = (
    # sheet goods
    "sperrholz", "tischlerplatte", "multiplexplatte", "siebdruckplatte", "mdf-platte",
    "spanplatte-", "osb3", "osb-", "leimholzplatte", "moebelbauplatte",
    # glue, cabinet hardware and edging
    "holzleim", "topfscharnier", "vollauszug", "schubladen", "spanplattenschraube", "umleimer",
    # tiling
    "fliesenkleber", "fugenmoertel", "fliesenschneider",
)

TOOM: Final = RetailSource(
    name="toom",
    base_url="https://toom.de",
    sitemap_urls=(
        "https://static.toom.de/sitemap/categories.xml",
        "https://static.toom.de/sitemap/cms/pages-0.xml",
        "https://static.toom.de/sitemap/cms/pages-1.xml",
        # Product detail pages (retail-ingestion "representative permitted
        # products"). robots.txt disallows none of `/p/` on 2026-09-23.
        "https://static.toom.de/sitemap/products-1-1.xml",
        "https://static.toom.de/sitemap/products-1-2.xml",
        "https://static.toom.de/sitemap/products-1-3.xml",
    ),
    groups=(
        # Delivery, returns and the cut service: the questions a shopper asks
        # that no product page answers. First, so a policy URL is never
        # counted in another group.
        SourceGroup(
            "policy",
            _patterns(r"/hilfe/", r"/service/bestell-lieferservice", r"/service/services-im-markt"),
            share=0.05,
        ),
        # Sheet goods, timber, fixings and tiling — what the cut and supply
        # lists are built from.
        SourceGroup(
            "categories",
            _patterns(
                r"/c/bauen-renovieren/holz",
                r"/c/bauen-renovieren/baustoffe",
                r"/c/bauen-renovieren/fliesen",
                r"/c/werkstatt-maschinen/eisenwaren-beschlaege",
            ),
            share=0.25,
        ),
        SourceGroup(
            "products",
            _patterns(rf"/p/[^/]*(?:{'|'.join(_PRODUCT_KEYWORDS)})"),
            share=0.40,
            buckets=tuple(re.compile(rf"/p/[^/]*{keyword}") for keyword in _PRODUCT_KEYWORDS),
        ),
        # toom's guides live under /selbermachen/, not /ratgeber/ (checked
        # 2026-09-23): the three topics a joinery workshop asks about.
        SourceGroup("guides_tiling", _patterns(r"/selbermachen/bad-sanitaer/fliesen/"), share=0.10),
        SourceGroup("guides_workshop", _patterns(r"/selbermachen/werkstatt-maschinen/"), share=0.10),
        SourceGroup("guides_building", _patterns(r"/selbermachen/bauen-renovieren/"), share=0.10),
    ),
)

BY_NAME: Final = {TOOM.name: TOOM}


def get_source(name: str) -> RetailSource:
    try:
        return BY_NAME[name]
    except KeyError:
        raise LookupError(
            f"no ingestion source is defined for {name!r}; "
            f"defined sources are {', '.join(sorted(BY_NAME))}"
        ) from None
