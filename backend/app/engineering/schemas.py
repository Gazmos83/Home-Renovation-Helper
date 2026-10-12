"""Strict source/evidence contracts. A model cannot authorise their use."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Collection(StrEnum):
    FUNDAMENTALS = "engineering_fundamentals"
    MATERIALS = "material_datasheets"
    HARDWARE = "hardware_manuals"
    STANDARDS = "furniture_standards_index"
    LAW = "eu_de_berlin_law"
    SAFETY = "product_safety"
    MURPHY_BED = "murphy_bed_safety"
    # Kitchen namespaces (additive; dual-tag overlapping sources onto the seven above).
    KITCHEN_CABINET = "kitchen_cabinet_engineering"
    KITCHEN_DRAWER = "kitchen_drawer_systems"
    KITCHEN_HINGE = "kitchen_hinges_hardware"
    KITCHEN_PANEL = "kitchen_panel_materials"
    KITCHEN_CONNECTION = "kitchen_cabinet_connections"
    KITCHEN_ANCHOR = "kitchen_wall_anchoring"
    KITCHEN_ERGONOMICS = "kitchen_ergonomics_accessibility"
    KITCHEN_MOISTURE = "kitchen_moisture_protection"
    KITCHEN_APPLIANCE = "kitchen_appliance_integration"
    KITCHEN_VALIDATION = "kitchen_structural_validation"


# Existing collections that remain the primary identity for overlapping kitchen sources.
KITCHEN_DUAL_TAGS: dict[Collection, tuple[Collection, ...]] = {
    Collection.KITCHEN_PANEL: (Collection.MATERIALS,),
    Collection.KITCHEN_DRAWER: (Collection.HARDWARE,),
    Collection.KITCHEN_HINGE: (Collection.HARDWARE,),
    Collection.KITCHEN_VALIDATION: (Collection.STANDARDS,),
    Collection.KITCHEN_ANCHOR: (Collection.HARDWARE, Collection.SAFETY),
    Collection.KITCHEN_CABINET: (Collection.FUNDAMENTALS,),
    Collection.KITCHEN_CONNECTION: (Collection.FUNDAMENTALS,),
    Collection.KITCHEN_MOISTURE: (Collection.FUNDAMENTALS, Collection.MATERIALS),
    Collection.KITCHEN_ERGONOMICS: (Collection.STANDARDS,),
    Collection.KITCHEN_APPLIANCE: (),
}

KITCHEN_COLLECTIONS: frozenset[Collection] = frozenset(KITCHEN_DUAL_TAGS)


def with_dual_tags(collections: list[Collection]) -> list[Collection]:
    """Expand kitchen namespaces with their mapped existing collections; preserve order."""
    seen: set[Collection] = set()
    expanded: list[Collection] = []
    for item in collections:
        for candidate in (item, *KITCHEN_DUAL_TAGS.get(item, ())):
            if candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded


class Scope(StrEnum):
    EXTRACT = "extraction"
    EMBED = "local_embedding"
    RETRIEVE = "local_retrieval"
    REMOTE = "remote_model_use"
    RETAIN = "retention"
    COMMERCIAL = "commercial_use"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class SourceMetadata(StrictModel):
    publisher: str | None = Field(default=None, max_length=300)
    title: str = Field(min_length=1, max_length=300)
    source_url: str | None = None
    standard_or_model: str | None = Field(default=None, max_length=200)
    edition: str | None = Field(default=None, max_length=200)
    retrieved_at: datetime | None = None
    jurisdiction: str | None = Field(default=None, max_length=200)
    applicable_furniture: list[str] | None = None
    material_grade: str | None = Field(default=None, max_length=200)
    thickness_mm: float | None = Field(default=None, gt=0)
    license_status: str | None = None
    page_section: str | None = None
    verification_status: Literal["unverified", "needs_review", "verified"] = (
        "unverified"
    )
    language: Literal["en", "de", "other"] | None = None
    # Kitchen / product extensions — nullable for legacy catalogue rows.
    source_kind: str | None = Field(default=None, max_length=120)
    approved_for_embedding: bool = False
    manufacturer: str | None = Field(default=None, max_length=200)
    part_number: str | None = Field(default=None, max_length=200)
    variant: str | None = Field(default=None, max_length=200)
    nominal_load_kg: float | None = Field(default=None, gt=0)
    runner_length_mm: float | None = Field(default=None, gt=0)
    drawer_width_mm: float | None = Field(default=None, gt=0)
    drawer_depth_mm: float | None = Field(default=None, gt=0)
    door_height_mm: float | None = Field(default=None, gt=0)
    door_mass_kg: float | None = Field(default=None, gt=0)
    panel_thickness_mm: float | None = Field(default=None, gt=0)
    mounting_conditions: str | None = Field(default=None, max_length=500)

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value: str | None) -> str | None:
        from urllib.parse import urlsplit

        if value is not None:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 443)
            ):
                raise ValueError(
                    "source_url must be HTTPS without credentials or a custom port"
                )
        return value


class SourceIn(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,119}$")
    metadata: SourceMetadata
    collections: list[Collection] = Field(min_length=1)


class Grant(StrictModel):
    pages: list[int] | None = None
    blocks: list[str] | None = None

    @field_validator("pages")
    @classmethod
    def physical_pages(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (not value or any(page < 1 for page in value)):
            raise ValueError(
                "pages must be a nonempty list of physical page numbers starting at 1"
            )
        return value

    @field_validator("blocks")
    @classmethod
    def block_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or any(not item.strip() for item in value)):
            raise ValueError("blocks must contain nonblank block identifiers")
        return value


class RightsIn(StrictModel):
    action: Literal["approve", "revoke"]
    grants: dict[Scope, Grant] = Field(default_factory=dict)
    evidence: str = Field(min_length=1, max_length=4000)
    reviewer: str = Field(min_length=1, max_length=200)
    use_context: Literal["personal_home", "commercial"] = "personal_home"
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def complete_decision(self) -> Self:
        if self.action == "approve" and not self.grants:
            raise ValueError("grants: approval needs at least one operation scope")
        if self.action == "revoke" and self.grants:
            raise ValueError("grants: revocation cannot grant operations")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at requires a timezone")
        extraction = self.grants.get(Scope.EXTRACT)
        if extraction is not None and extraction.blocks is not None:
            raise ValueError(
                "extraction uses page scopes; block IDs are only known after extraction"
            )
        return self


class ReviewIn(StrictModel):
    reviewer: str = Field(min_length=1, max_length=200)
    status: Literal["unverified", "needs_review", "verified"]


class EvidenceBlock(StrictModel):
    block_id: str = Field(min_length=1, max_length=120)
    kind: Literal["paragraph", "table", "equation", "unreadable"]
    content: str = Field(min_length=1)
    pages: list[int] = Field(default_factory=list)
    printed_pages: list[str] = Field(default_factory=list)
    section: str | None = None
    headers: list[str] = Field(default_factory=list)
    footnotes: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    verification_status: Literal["unverified", "needs_review", "verified"] = (
        "unverified"
    )
    reviewed_by: str | None = None

    @model_validator(mode="after")
    def reviewed(self) -> Self:
        if self.verification_status == "verified" and (
            not self.reviewed_by or (not self.pages and not self.section)
        ):
            raise ValueError(
                "verified blocks require reviewer and page/section provenance"
            )
        if self.kind == "unreadable" and self.verification_status == "verified":
            raise ValueError("unreadable blocks cannot be verified")
        return self


class PropertyIn(StrictModel):
    block_id: str = Field(min_length=1, max_length=120)
    kind: Literal[
        "E_MPa",
        "bending_strength_MPa",
        "density_kg_m3",
        "capacity_N",
        "thickness_mm",
        "allowable_span_mm",
    ]
    value: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    original_unit: str
    original_value: float | None = None
    original_minimum: float | None = None
    original_maximum: float | None = None
    value_basis: Literal[
        "mean",
        "characteristic",
        "allowable",
        "manufacturer_rating",
        "nominal",
        "unknown",
    ] = "unknown"
    standard_or_model: str | None = None
    material_grade: str | None = None
    thickness_mm: float | None = Field(default=None, gt=0)
    page_section: str = Field(min_length=1)
    test_method: str | None = None
    conditions: dict[str, str | float | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def units_and_range(self) -> Self:
        units = {
            "E_MPa": {"MPa": 1, "GPa": 1000, "Pa": 0.000001},
            "bending_strength_MPa": {"MPa": 1, "GPa": 1000, "Pa": 0.000001},
            "density_kg_m3": {"kg/m3": 1, "g/cm3": 1000},
            "capacity_N": {"N": 1, "kN": 1000, "kg": 9.81},
            "thickness_mm": {"mm": 1, "m": 1000},
            "allowable_span_mm": {"mm": 1, "m": 1000},
        }
        if self.original_unit not in units[self.kind]:
            raise ValueError("original_unit is not valid for the property kind")
        factor = units[self.kind][self.original_unit]
        for canonical, original in (
            ("value", "original_value"),
            ("minimum", "original_minimum"),
            ("maximum", "original_maximum"),
        ):
            raw = getattr(self, original)
            converted = raw * factor if raw is not None else None
            if converted is not None and not isfinite(converted):
                raise ValueError(f"{canonical} conversion is non-finite")
            provided = getattr(self, canonical)
            if provided is not None and (
                converted is None
                or abs(provided - converted) > max(1e-9, abs(converted) * 1e-9)
            ):
                raise ValueError(f"{canonical} disagrees with original value/unit")
            setattr(self, canonical, converted)
        if self.value is not None and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("value and range are mutually exclusive")
        if (self.minimum is None) != (self.maximum is None):
            raise ValueError("range requires both bounds")
        if self.minimum is not None and self.minimum > self.maximum:
            raise ValueError("minimum exceeds maximum")
        if any(
            value is not None and value <= 0
            for value in (self.value, self.minimum, self.maximum)
        ):
            raise ValueError("property values must be positive; unknown is null")
        return self


class SearchFilters(StrictModel):
    collection: Collection | None = None
    jurisdiction: str | None = None
    furniture: str | None = None
    edition: str | None = None
    standard_or_model: str | None = None
    material_grade: str | None = None
    thickness_mm: float | None = Field(default=None, gt=0)


class SearchIn(StrictModel):
    query: str = Field(min_length=1, max_length=400)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=20)
    min_relevance: float | None = Field(default=None, ge=0, le=1)
