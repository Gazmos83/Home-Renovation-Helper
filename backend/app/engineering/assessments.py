"""Owner-confirmed facts, with explicit dimensions, units and unresolved inputs."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.engineering.schemas import StrictModel

Status = Literal["PASS_FOR_STATED_CASE", "FAIL_FOR_STATED_CASE", "NOT_VERIFIED"]
Family = Literal[
    "shelf_immediate",
    "shelf_creep",
    "joint",
    "hardware",
    "anchor",
    "tipping",
    "countertop",
    "murphy",
]


class Quantity(StrictModel):
    value: float = Field(gt=0)
    unit: Literal["mm", "m", "kg", "N", "kN", "MPa", "N/m", "N/mm", "kg/m"]

    def canonical(self) -> dict:
        conversion = {
            "mm": (0.001, "m"),
            "m": (1, "m"),
            "kg": (1, "kg"),
            "N": (1, "N"),
            "kN": (1000, "N"),
            "MPa": (1_000_000, "Pa"),
            "N/m": (1, "N/m"),
            "N/mm": (1000, "N/m"),
            "kg/m": (9.81, "N/m"),
        }
        factor, unit = conversion[self.unit]
        from math import isfinite

        value = self.value * factor
        if not isfinite(value):
            raise ValueError("canonical unit conversion is non-finite")
        return {
            "value": value,
            "unit": unit,
            "original_value": self.value,
            "original_unit": self.unit,
            "conversion_factor": factor,
        }

    def force(self) -> dict:
        if self.unit not in {"kg", "N", "kN"}:
            raise ValueError("load requires kg, N or kN")
        result = self.canonical()
        if self.unit == "kg":
            result.update(
                value=self.value * 9.81,
                unit="N",
                conversion_factor=9.81,
                conversion="F_N = mass_kg × 9.81",
            )
            from math import isfinite

            if not isfinite(result["value"]):
                raise ValueError("mass-to-force conversion is non-finite")
        return result


class Binding(StrictModel):
    part_id: str = Field(min_length=1, max_length=120)
    standard_or_model: str | None = None
    material_grade: str | None = None
    thickness_mm: float | None = Field(default=None, gt=0)
    property_ids: list[UUID] = Field(default_factory=list, max_length=20)
    manual_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    hardware_model: str | None = None
    hardware_revision: str | None = None
    hardware_count: int | None = Field(default=None, gt=0)
    orientation: str | None = None
    load_distribution_evidence_id: str | None = None
    # Owner-selected loads/supports remain assumptions, not verified ratings.
    load: Quantity | None = None
    support: Literal["simply_supported", "cantilever", "other"] | None = None
    support_positions: list[float] | None = None
    support_path: str | None = None

    @model_validator(mode="after")
    def load_units(self) -> Self:
        if self.load is not None:
            self.load.force() if self.load.unit in {
                "kg",
                "N",
                "kN",
            } else self.distributed_load()
        if self.support_positions is not None:
            from math import isfinite

            if not self.support_positions or any(
                not isfinite(value) or value < 0 for value in self.support_positions
            ):
                raise ValueError(
                    "support_positions require finite nonnegative coordinates in metres"
                )
        return self

    def distributed_load(self) -> dict:
        if self.load.unit not in {"N/m", "N/mm", "kg/m"}:
            raise ValueError("load requires mass/force or a distributed force unit")
        return self.load.canonical()


class AssessmentIn(StrictModel):
    version: int = Field(ge=1)
    furniture: Literal[
        "shelf",
        "wall_cabinet",
        "entertainment_unit",
        "countertop",
        "murphy_bed",
        "kitchen_base_cabinet",
        "kitchen_wall_cabinet",
        "kitchen_tall_cabinet",
        "kitchen_drawer",
        "kitchen_worktop",
        "other",
    ]
    bindings: list[Binding] = Field(default_factory=list, max_length=50)
    duration: str | None = None
    moisture_service: str | None = None
    sustained_load_share: float | None = Field(default=None, ge=0, le=1)
    temperature_c: float | None = None
    wall_substrate: str | None = None
    anchor_model: str | None = None
    anchor_approval_evidence_id: str | None = None
    embedment_mm: float | None = Field(default=None, gt=0)
    edge_distance_mm: float | None = Field(default=None, gt=0)
    spacing_mm: float | None = Field(default=None, gt=0)
    load_transfer: str | None = None
    tv_mass: Quantity | None = None
    accessory_mass: Quantity | None = None
    footprint_mm: list[float] | None = Field(default=None, min_length=2, max_length=2)
    centre_of_gravity_mm: list[float] | None = Field(
        default=None, min_length=3, max_length=3
    )
    misuse_load_case_evidence_id: str | None = None
    countertop_model: str | None = None
    countertop_manual_evidence_id: str | None = None
    countertop_overhang_mm: float | None = Field(default=None, ge=0)
    countertop_cutouts: str | None = None
    countertop_supports: str | None = None
    mechanism_model: str | None = None
    mechanism_revision: str | None = None
    mechanism_manual_evidence_id: str | None = None
    qualified_installation_review: str | None = None
    owner_assumptions: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def geometry_and_mass_units(self) -> Self:
        if len({binding.part_id for binding in self.bindings}) != len(self.bindings):
            raise ValueError("one exact binding per part is required")
        for field in ("tv_mass", "accessory_mass"):
            quantity = getattr(self, field)
            if quantity is not None and quantity.unit != "kg":
                raise ValueError(f"{field} must declare kg, not force")
        if self.footprint_mm and any(value <= 0 for value in self.footprint_mm):
            raise ValueError("footprint dimensions must be positive")
        return self


class CheckResult(StrictModel):
    method_id: str
    method_version: str
    status: Status = "NOT_VERIFIED"
    part_id: str | None = None
    case: str | None = None
    result: float | None = None
    unit: str | None = None
    limit: float | None = Field(default=None, gt=0)
    utilisation: float | None = Field(default=None, ge=0)
    criterion: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def criterion_before_pass(self) -> Self:
        if self.result is not None and (not self.unit or not self.unit.strip()):
            raise ValueError("a numerical result requires its explicit unit")
        if self.status != "NOT_VERIFIED" and (
            self.result is None
            or self.limit is None
            or not self.criterion
            or not self.source_evidence_ids
        ):
            raise ValueError(
                "a verification result requires value, limit, cited criterion and evidence"
            )
        return self


class CalculationReport(StrictModel):
    checks: list[CheckResult]
    # No SAFE or whole-piece PASS status exists.
    overall: Literal["INCOMPLETE", "COMPLETE_FOR_STATED_CASES"]
    assumptions: list[str]
    review_requirements: list[str]
    conformity: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"

    @model_validator(mode="after")
    def incomplete_if_unresolved(self) -> Self:
        if self.overall == "COMPLETE_FOR_STATED_CASES" and (
            not self.checks
            or any(check.status == "NOT_VERIFIED" for check in self.checks)
            or self.review_requirements
        ):
            raise ValueError(
                "unresolved checks/reviews keep the overall assessment incomplete"
            )
        return self
