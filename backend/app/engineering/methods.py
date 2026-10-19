"""Closed version registry. No formula is enabled without its source/review package."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from math import isfinite

from app.engineering.assessments import CheckResult
from app.engineering.registry import EvidenceRefused


@dataclass(frozen=True)
class Criterion:
    id: str
    limit: float
    unit: str
    source_evidence_id: str

    def __post_init__(self):
        if (
            not self.id.strip()
            or not self.unit.strip()
            or not self.source_evidence_id.strip()
            or not isfinite(self.limit)
            or self.limit <= 0
        ):
            raise ValueError(
                "criterion requires an identifiable finite positive source-backed limit"
            )


@dataclass(frozen=True)
class Method:
    id: str
    version: str
    units: tuple[str, ...]
    required_inputs: tuple[str, ...]
    domain: str
    citation_evidence_ids: tuple[str, ...] = ()
    criteria: tuple[Criterion, ...] = ()
    independent_reference_cases: tuple[dict, ...] = ()
    # Assigned only by reviewed code changes; no user/model expression is run.
    implementation: Callable | None = None
    range_rule: str | None = None

    @property
    def definition(self) -> dict:
        return {
            key: value for key, value in asdict(self).items() if key != "implementation"
        }

    @property
    def releasable(self) -> bool:
        return bool(
            self.implementation
            and self.citation_evidence_ids
            and self.criteria
            and all(
                item.source_evidence_id in self.citation_evidence_ids
                for item in self.criteria
            )
            and self.independent_reference_cases
        )


# Hyman, "Down With Sagging Shelves", JLC April 1995; owner-reviewed blocks.
HYMAN_1995 = "1a422636-e859-4c69-8cc0-a52a9d7d90cc"
HYMAN_FORMULA = f"{HYMAN_1995}:hyman-p80-deflection-formula"
HYMAN_EXAMPLE = f"{HYMAN_1995}:hyman-p80-worked-example"
HYMAN_SPANS = f"{HYMAN_1995}:hyman-p84-allowable-spans-table"


def shelf_immediate_deflection(
    span_m: float,
    width_m: float,
    thickness_m: float,
    load_N_per_m: float,
    E_Pa: float,
) -> dict:
    """Immediate elastic midspan deflection of a simply supported shelf under uniform load.

    d = 5/384 · wL⁴ / (EI), I = b·h³ / 12 (Hyman 1995, sidebar). SI in, SI out.
    """
    values = (span_m, width_m, thickness_m, load_N_per_m, E_Pa)
    if any(not isfinite(value) or value <= 0 for value in values):
        raise EvidenceRefused(
            "inputs", "finite positive span, section, load and E are required"
        )
    I_m4 = width_m * thickness_m**3 / 12
    deflection_m = 5 / 384 * load_N_per_m * span_m**4 / (E_Pa * I_m4)
    if not isfinite(deflection_m):
        raise EvidenceRefused("inputs", "deflection is non-finite")
    return {
        "I_m4": I_m4,
        "deflection_m": deflection_m,
        "deflection_span_ratio": deflection_m / span_m,
    }


METHODS = {
    method.id: method
    for method in (
        Method(
            "shelf_immediate",
            "1",
            ("m", "N/m", "Pa"),
            (
                "span",
                "section",
                "supports",
                "load_distribution",
                "E_MPa",
            ),
            "Rectangular prismatic shelf, simply supported at its two ends, under a uniform distributed load; immediate elastic deflection against L/400 only. Bending strength is not checked. No folds, polygons, cantilevers, point loads or assumed divider support",
            citation_evidence_ids=(HYMAN_FORMULA, HYMAN_EXAMPLE, HYMAN_SPANS),
            criteria=(Criterion("deflection_span_ratio", 1 / 400, "m/m", HYMAN_SPANS),),
            independent_reference_cases=(
                {
                    "source_evidence_id": HYMAN_EXAMPLE,
                    "inputs": {
                        "span_in": 26,
                        "width_in": 8.5,
                        "thickness_in": 0.56,
                        "load_lb_per_in": 2.9,
                        "E_psi": 350_000,
                    },
                    "expected": {"I_in4": 0.1244, "deflection_in": 0.40},
                    "tolerance": "as printed (two significant figures)",
                },
            ),
            implementation=shelf_immediate_deflection,
        ),
        Method(
            "shelf_creep",
            "1",
            ("m", "N", "Pa"),
            (
                "immediate_case",
                "material_grade",
                "creep_model",
                "duration",
                "moisture_service",
                "sustained_load_share",
            ),
            "Exact reviewed material/service/duration creep domain",
        ),
        Method(
            "joint",
            "1",
            ("m", "N"),
            (
                "joint_type",
                "fastener",
                "edge_distances",
                "load_direction",
                "tested_assembly",
            ),
            "Exact reviewed joint or tested assembly; no generic confirmat rating",
        ),
        Method(
            "hardware",
            "1",
            ("N",),
            ("model", "revision", "orientation", "count", "documented_distribution"),
            "Exact manufacturer rating and installation with reviewed load sharing",
        ),
        Method(
            "anchor",
            "1",
            ("m", "N"),
            (
                "approval",
                "substrate",
                "edge_distance",
                "spacing",
                "embedment",
                "tension",
                "shear",
                "load_transfer",
            ),
            "Exact approval, substrate and reviewed tension/shear interaction",
        ),
        Method(
            "tipping",
            "1",
            ("m", "kg", "N"),
            (
                "footprint",
                "mass",
                "centre_of_gravity",
                "TV_accessories",
                "misuse_load_cases",
            ),
            "Declared footprint and sourced foreseeable-use load cases",
        ),
        Method(
            "countertop",
            "1",
            ("m", "N"),
            ("exact_product", "thickness", "manual", "overhang", "cutouts", "supports"),
            "Exact-product instructions; no general stone solver",
        ),
        Method(
            "murphy",
            "1",
            ("m", "N"),
            (
                "mechanism_model",
                "revision",
                "manual",
                "wall_anchor_assessment",
                "qualified_review",
            ),
            "Individual stated checks only; no whole-bed approval or mechanism certification",
        ),
    )
}


def method(identifier: str, version: str = "1") -> Method:
    selected = METHODS.get(identifier)
    if selected is None or selected.version != version:
        raise EvidenceRefused("method_id", "unknown closed method/version")
    return selected


def allowable_property(prop, selected: Method) -> float:
    """No midpoint or inferred safety factor can convert a test value to resistance."""
    record = prop.record
    if record.get("kind") not in {"bending_strength_MPa", "capacity_N"}:
        raise EvidenceRefused(
            "kind",
            "a resistance property is required; stiffness/density is not allowable resistance",
        )
    if prop.verification_status != "verified" or record["value_basis"] not in {
        "allowable",
        "manufacturer_rating",
    }:
        raise EvidenceRefused(
            "value_basis",
            "verified allowable resistance or exact manufacturer rating is required",
        )
    if record["value"] is None:
        raise EvidenceRefused(
            "range",
            "range needs method-specific qualified bound propagation; no midpoint is permitted",
        )
    value = record["value"]
    if not isfinite(value) or value <= 0:
        raise EvidenceRefused("value", "finite positive resistance is required")
    return value


def stiffness_property(prop: dict) -> float:
    """A verified single E value in Pa; a range has no reviewed bound rule here."""
    record = prop["record"]
    if record.get("kind") != "E_MPa":
        raise EvidenceRefused("kind", "a modulus of elasticity (E_MPa) is required")
    if prop["verification_status"] != "verified" or record["value_basis"] == "unknown":
        raise EvidenceRefused(
            "value_basis", "verified E with a stated value basis is required"
        )
    if record["value"] is None:
        raise EvidenceRefused(
            "range", "E range has no reviewed bound rule; no midpoint is permitted"
        )
    return record["value"] * 1_000_000


def compare_result(
    selected: Method,
    review_state: dict,
    result: float,
    criterion_id: str,
    *,
    part_id: str | None = None,
) -> CheckResult:
    """Classify a code-computed demand against an exact reviewed maximum.

    This comparison is infrastructure, not an engineering equation. Its inputs
    never come from model-authored answer/status fields. Real method domains and
    criteria still need their independent source/review packages.
    """
    from app.engineering.geometry import digest

    criterion = next(
        (item for item in selected.criteria if item.id == criterion_id), None
    )
    if (
        not selected.releasable
        or not review_state.get("enabled")
        or review_state.get("qualified_review_state") != "accept"
        or review_state.get("definition_hash") != digest(selected.definition)
        or criterion is None
    ):
        return CheckResult(
            method_id=selected.id,
            method_version=selected.version,
            part_id=part_id,
            missing_inputs=[
                "enabled qualified method and exact reviewed acceptance criterion are required"
            ],
        )
    if not isfinite(result) or result < 0 or not isfinite(result / criterion.limit):
        return CheckResult(
            method_id=selected.id,
            method_version=selected.version,
            part_id=part_id,
            missing_inputs=[
                "finite nonnegative result within the reviewed domain is required"
            ],
        )
    return CheckResult(
        method_id=selected.id,
        method_version=selected.version,
        part_id=part_id,
        status="PASS_FOR_STATED_CASE"
        if result <= criterion.limit
        else "FAIL_FOR_STATED_CASE",
        result=result,
        unit=criterion.unit,
        limit=criterion.limit,
        utilisation=result / criterion.limit,
        criterion=criterion.id,
        source_evidence_ids=[criterion.source_evidence_id],
    )


def unavailable(
    identifier: str, *, part_id: str | None = None, missing: list[str] | None = None
) -> CheckResult:
    selected = method(identifier)
    return CheckResult(
        method_id=selected.id,
        method_version=selected.version,
        part_id=part_id,
        missing_inputs=[
            "method unavailable: cited equations/criteria, independent reference cases and qualified review are required",
            *(missing or []),
        ],
    )
