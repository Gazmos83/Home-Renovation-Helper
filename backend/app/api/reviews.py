"""Reviews of a package version (render-review). Owner-gated.

A review is recorded by the Reviewer in conversation. These routes only read a
version's reviews and let the owner mark an item resolved or dismissed. Nothing
here starts a review, a build or a render, and no response carries a model slug.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_owner
from app.api.packages import not_found
from app.blender import storage
from app.db.models import Review, ReviewItem

version_router = APIRouter(
    prefix="/packages", tags=["reviews"], dependencies=[Depends(require_owner)]
)
item_router = APIRouter(
    prefix="/reviews", tags=["reviews"], dependencies=[Depends(require_owner)]
)


class ReviewItemOut(BaseModel):
    id: UUID
    ordinal: int
    aspect: str
    expected: str
    expected_source: str
    rule_id: str | None
    observed: str
    image: int
    severity: str
    suggestion: str | None
    status: str
    status_at: datetime | None


class ReviewOut(BaseModel):
    id: UUID
    package_id: str
    version: int
    renders: list[str]
    created_at: datetime
    items: list[ReviewItemOut]


class ItemStatusIn(BaseModel):
    status: Literal["resolved", "dismissed"]


def _item_out(item: ReviewItem) -> ReviewItemOut:
    return ReviewItemOut(
        id=item.id,
        ordinal=item.ordinal,
        aspect=item.aspect,
        expected=item.expected,
        expected_source=item.expected_source,
        rule_id=item.rule_id,
        observed=item.observed,
        image=item.image,
        severity=item.severity,
        suggestion=item.suggestion,
        status=item.status,
        status_at=item.status_at,
    )


def _review_out(review: Review, items: list[ReviewItem]) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        package_id=review.package_id,
        version=review.version,
        renders=list(review.renders or []),
        created_at=review.created_at,
        items=[_item_out(item) for item in items],
    )


@version_router.get("/{package_id}/versions/{version}/reviews")
def list_reviews(package_id: str, version: int, request: Request) -> list[ReviewOut]:
    if version < 1:
        raise not_found()
    try:
        storage.validate_package_id(package_id)
    except storage.InvalidPackageId:
        raise not_found() from None
    with Session(request.app.state.engine) as session:
        reviews = house_file.reviews_for(session, package_id, version)
        return [_review_out(review, house_file.items_of(session, review.id)) for review in reviews]


@item_router.patch("/{review_id}/items/{item_id}")
def set_item_status(
    review_id: UUID, item_id: UUID, body: ItemStatusIn, request: Request
) -> ReviewItemOut:
    with Session(request.app.state.engine) as session:
        review = house_file.get_review(session, review_id)
        item = house_file.get_item(session, item_id)
        if review is None or item is None or item.review_id != review.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        updated = house_file.set_item_status(session, item_id, body.status)
        session.commit()
        session.refresh(updated)
        return _item_out(updated)
