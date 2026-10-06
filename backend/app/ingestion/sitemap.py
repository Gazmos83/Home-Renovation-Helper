"""Sitemap-driven URL discovery.

Discovery reads the index a site publishes for exactly this purpose rather
than following links: it is bounded, it costs a handful of requests, and it
cannot wander into paths the rules exclude (design.md decision 3).

Sitemap XML is third-party data. It is parsed for locations and nothing else —
no entity resolution, no network references followed beyond the nested
sitemaps a sitemap index legitimately declares.
"""

from __future__ import annotations

import logging
import re

from defusedxml import ElementTree as SafeElementTree  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_LOC = re.compile(r"\{.*\}loc$|^loc$")


def parse_locations(xml_text: str) -> tuple[str, list[str]]:
    """Return (kind, locations) where kind is 'index' or 'urlset'."""
    root = SafeElementTree.fromstring(xml_text)
    tag = root.tag.rsplit("}", 1)[-1]
    kind = "index" if tag == "sitemapindex" else "urlset"
    locations = [
        element.text.strip()
        for element in root.iter()
        if _LOC.search(element.tag) and element.text and element.text.strip()
    ]
    return kind, locations
