"""Owner-scoped report reads and developer-only method-review controls."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.gate import require_dev, require_owner
from app.db.models import (
    EngineeringAssessment,
    EngineeringCalculationReport,
    EngineeringMethodReview,
    PieceVersion,
)
from app.engineering.geometry import digest
from app.engineering.methods import METHODS, method
from app.engineering.registry import EvidenceRefused
from app.engineering.reports import method_state, report_copy, stale_reasons
from app.engineering.retrieval import resolve_evidence
from app.engineering.schemas import StrictModel

router = APIRouter(
    prefix="/packages", tags=["engineering"], dependencies=[Depends(require_owner)]
)
admin_router = APIRouter(
    prefix="/admin/engineering-methods",
    tags=["admin"],
    dependencies=[Depends(require_dev)],
)


@router.get("/{package_id}/versions/{version}/engineering/reports")
def reports(package_id: str, version: int, request: Request):
    with Session(request.app.state.engine) as session:
        if session.get(PieceVersion, (package_id, version)) is None:
            raise HTTPException(404, detail="Not Found")
        rows = session.scalars(
            select(EngineeringCalculationReport)
            .where(
                EngineeringCalculationReport.package_id == package_id,
                EngineeringCalculationReport.version == version,
            )
            .order_by(EngineeringCalculationReport.created_at.desc())
        )
        return [
            report_copy(
                session,
                request.app.state.settings.render_root,
                row.id,
                package_id=package_id,
            )
            for row in rows
        ]


@router.get("/{package_id}/versions/{version}/engineering/reports/{report_id}")
def report(package_id: str, version: int, report_id: UUID, request: Request):
    with Session(request.app.state.engine) as session:
        result = report_copy(
            session,
            request.app.state.settings.render_root,
            report_id,
            package_id=package_id,
        )
        if result is None or result["version"] != version:
            raise HTTPException(404, detail="Not Found")
        return result


@router.get("/{package_id}/versions/{version}/engineering/assessments")
def assessments(package_id: str, version: int, request: Request):
    with Session(request.app.state.engine) as session:
        if session.get(PieceVersion, (package_id, version)) is None:
            raise HTTPException(404, detail="Not Found")
        return [
            {
                "assessment_id": str(row.id),
                "version": row.version,
                "input_hash": row.input_hash,
                "spec_hash": row.spec_hash,
                "stale_reasons": stale_reasons(
                    session, request.app.state.settings.render_root, row
                ),
            }
            for row in session.scalars(
                select(EngineeringAssessment)
                .where(
                    EngineeringAssessment.package_id == package_id,
                    EngineeringAssessment.version == version,
                )
                .order_by(EngineeringAssessment.sequence.desc())
            )
        ]


@admin_router.get("")
def methods(request: Request):
    with Session(request.app.state.engine) as session:
        return [
            {
                **item.definition,
                **method_state(session, item.id),
                "releasable": item.releasable,
                "limitation": "Exact equations, criteria, independent references and qualified review are pending"
                if not item.releasable
                else None,
            }
            for item in METHODS.values()
        ]


class MethodReviewIn(StrictModel):
    method_version: str = "1"
    definition_hash: str = Field(min_length=64, max_length=64)
    action: Literal["pending", "accept", "disable"]
    reviewer: str = Field(min_length=1, max_length=200)
    qualification_evidence: str = Field(min_length=1, max_length=4000)
    evidence: str = Field(min_length=1, max_length=4000)

    @field_validator("reviewer", "qualification_evidence", "evidence")
    @classmethod
    def documented_review(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reviewer and supporting review evidence cannot be blank")
        return value.strip()


@admin_router.post("/{method_id}/review")
def review(method_id: str, data: MethodReviewIn, request: Request):
    with Session(request.app.state.engine) as session:
        try:
            selected = method(method_id, data.method_version)
            if data.definition_hash != digest(selected.definition):
                raise EvidenceRefused(
                    "definition_hash",
                    "review must identify the exact current method definition",
                )
            if data.action == "accept":
                from app.engineering.release import release_ready

                if (
                    not release_ready()
                    or not selected.releasable
                    or any(
                        (packet := resolve_evidence(session, identifier, remote=False))
                        is None
                        or packet["metadata"]["verification_status"] != "verified"
                        or packet["block"]["verification_status"] != "verified"
                        for identifier in selected.citation_evidence_ids
                    )
                ):
                    raise EvidenceRefused(
                        "action",
                        "foundation acceptance, implemented method, reviewed cited criteria and independent references are required before qualified acceptance/enablement",
                    )
            session.add(
                EngineeringMethodReview(method_id=selected.id, **data.model_dump())
            )
            session.commit()
            return method_state(session, selected.id)
        except EvidenceRefused as error:
            raise HTTPException(
                422, detail={"field": error.field, "reason": error.reason}
            ) from None
