"""Approving a built piece version, the same way from the piece inspector and from the
Designer's `approve_version` (place-piece-from-owner-words)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent import decisions_note, house_file
from app.agent.tools.shared import read_input
from app.blender import storage
from app.blender.custom_build.derive import overall
from app.db.models import Piece, PieceVersion

logger = logging.getLogger("app")


class ApprovalRefused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def approve_built_version(session: Session, folder: Path, package_id: str, version: int) -> PieceVersion:
    """Approve a built, recorded version in the caller's transaction (the caller commits). A
    newly approved version drops superseded decision rows and raises the brief's height limit."""
    if (storage.read_status(folder) or {}).get("status") != "succeeded":
        raise ApprovalRefused("not_built", f"version {version} must be built before it can be approved")
    if house_file.version_row(session, package_id, version) is None:
        raise ApprovalRefused(
            "not_recorded",
            f"version {version} of {package_id!r} is not in the house file; "
            "only versions made in a conversation can be approved",
        )
    newly = house_file.version_row(session, package_id, version).approved_at is None
    row = house_file.approve_version(session, package_id, version)
    if newly:
        try:
            with session.begin_nested():
                decisions_note.drop_superseded_version_rows(session, package_id, version)
        except Exception:
            logger.exception("dropping superseded version rows failed for %s", package_id)
        try:
            with session.begin_nested():
                document = read_input(folder)
                if document is not None:
                    house_file.raise_brief_height_limit(session, package_id, version, overall(document)["h"])
                piece = session.get(Piece, package_id)
                limit = (piece.brief or {}).get("max_piece_height_mm") if piece else None
                if isinstance(limit, int | float) and not isinstance(limit, bool):
                    house_file.dismiss_outdated_height_items(session, package_id, version, limit)
        except Exception:
            logger.exception("raising the brief's height limit failed for %s", package_id)
    return row
