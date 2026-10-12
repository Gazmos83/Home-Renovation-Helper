"""Kitchen cabinet/drawer intent routing over the existing engineering collections."""

from __future__ import annotations

import re
from enum import StrEnum

from app.engineering.schemas import (
    KITCHEN_COLLECTIONS,
    KITCHEN_DUAL_TAGS,
    Collection,
    with_dual_tags,
)


class KitchenIntent(StrEnum):
    BASE_WALL_CABINET = "base_wall_cabinet"
    SINK_UNIT = "sink_unit"
    DRAWER = "drawer"
    HINGE = "hinge"
    HANGER_ANCHOR = "hanger_anchor"
    MOISTURE = "moisture"
    APPLIANCE = "appliance"
    ERGONOMICS = "ergonomics"
    WORKTOP = "worktop"


_INTENT_PATTERNS: dict[KitchenIntent, re.Pattern[str]] = {
    KitchenIntent.BASE_WALL_CABINET: re.compile(
        r"\b(base cabinet|wall cabinet|tall cabinet|kitchen cabinet|unterschrank|oberschrank|"
        r"hochschrank|küchenschrank|kuechenschrank|carcass|korpus)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.SINK_UNIT: re.compile(
        r"\b(sink unit|sink cabinet|spülenschrank|spuelenschrank|spüle|spuele)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.DRAWER: re.compile(
        r"\b(drawer|runner|slide|auszug|schublade|führung|fuehrung|vollauszug)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.HINGE: re.compile(
        r"\b(hinge|lift system|soft[- ]?close|scharnier|liftbeschlag|klappenbeschlag)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.HANGER_ANCHOR: re.compile(
        r"\b(hanger|anchor|anchors|wall rail|plasterboard|gipskarton|hängeschien|"
        r"haengeschien|dübel|duebel|veranker|wandbefestigung|wandschrank.*befest|"
        r"fixing)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.MOISTURE: re.compile(
        r"\b(moisture|humid|dishwasher|edge seal|quellung|feucht|spülmaschine|"
        r"spuelmaschine|versiegel|p2\b|p3\b|p5\b)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.APPLIANCE: re.compile(
        r"\b(oven|dishwasher|fridge|refrigerator|hob|cooktop|appliance|gerät|geraet|"
        r"backofen|kühlschrank|kuehlschrank|induktion|dunstabzug)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.ERGONOMICS: re.compile(
        r"\b(ergonomic|reach zone|working height|accessibility|barrierefrei|greifraum|"
        r"arbeitshöhe|arbeitshoehe|din\s*18040)\b",
        re.IGNORECASE,
    ),
    KitchenIntent.WORKTOP: re.compile(
        r"\b(worktop|countertop|arbeitsplatte|quartz|ceramic|steinplatte|overhang|"
        r"überstand|ueberstand)\b",
        re.IGNORECASE,
    ),
}

_INTENT_COLLECTIONS: dict[KitchenIntent, tuple[Collection, ...]] = {
    KitchenIntent.BASE_WALL_CABINET: (
        Collection.KITCHEN_CABINET,
        Collection.KITCHEN_CONNECTION,
        Collection.KITCHEN_VALIDATION,
    ),
    KitchenIntent.SINK_UNIT: (
        Collection.KITCHEN_CABINET,
        Collection.KITCHEN_MOISTURE,
        Collection.KITCHEN_APPLIANCE,
    ),
    KitchenIntent.DRAWER: (Collection.KITCHEN_DRAWER, Collection.KITCHEN_VALIDATION),
    KitchenIntent.HINGE: (Collection.KITCHEN_HINGE,),
    KitchenIntent.HANGER_ANCHOR: (
        Collection.KITCHEN_ANCHOR,
        Collection.KITCHEN_VALIDATION,
    ),
    KitchenIntent.MOISTURE: (Collection.KITCHEN_MOISTURE, Collection.KITCHEN_PANEL),
    KitchenIntent.APPLIANCE: (Collection.KITCHEN_APPLIANCE, Collection.KITCHEN_MOISTURE),
    KitchenIntent.ERGONOMICS: (Collection.KITCHEN_ERGONOMICS,),
    KitchenIntent.WORKTOP: (
        Collection.KITCHEN_CABINET,
        Collection.KITCHEN_VALIDATION,
        Collection.MATERIALS,
    ),
}

_CROSS_MANUFACTURER = re.compile(
    r"\b(blum)\b.*\b(hettich|häfele|hafele)\b|\b(hettich|häfele|hafele)\b.*\b(blum)\b|"
    r"\b(use|apply|nehmen)\b.{0,40}\b(blum)\b.{0,40}\b(hettich|häfele|hafele)\b",
    re.IGNORECASE,
)
_DIN_COMPLIANCE = re.compile(
    r"\b(din\s*en\s*14749|din\s*en\s*15939|din\s*en\s*16122).{0,40}\b("
    r"compliant|compliance|konform|erfüllt|erfuellt|confirmed|nachweis)\b|"
    r"\b(compliant|compliance|konform|erfüllt|erfuellt|confirmed).{0,40}\b("
    r"din\s*en\s*14749|din\s*en\s*15939)\b",
    re.IGNORECASE,
)


def kitchen_intents(text: str) -> list[KitchenIntent]:
    return [
        intent for intent, pattern in _INTENT_PATTERNS.items() if pattern.search(text)
    ]


def recommended_collections(text: str) -> list[Collection]:
    """Kitchen namespaces plus dual-tagged existing collections for a query."""
    intents = kitchen_intents(text)
    if not intents:
        return []
    selected: list[Collection] = []
    for intent in intents:
        selected.extend(_INTENT_COLLECTIONS[intent])
    return with_dual_tags(selected)


def refuses_cross_manufacturer(text: str) -> bool:
    return bool(_CROSS_MANUFACTURER.search(text))


def refuses_din_compliance_claim(text: str) -> bool:
    return bool(_DIN_COMPLIANCE.search(text))


def all_kitchen_namespaces() -> frozenset[Collection]:
    return KITCHEN_COLLECTIONS


def dual_tag_targets(collection: Collection) -> tuple[Collection, ...]:
    return KITCHEN_DUAL_TAGS.get(collection, ())
