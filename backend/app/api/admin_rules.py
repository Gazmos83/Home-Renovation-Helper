"""Developer panel: design rules over the checked-in table, and the open `TODO(user)` items (dev-panel-insights)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from app.api.gate import require_dev
from app.guidelines.checks import CHECKS
from app.guidelines.rule_overrides import (
    delete_override,
    effective_rules,
    save_override,
)
from app.guidelines.rules import DesignRulesError

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_dev)])

BACKEND: Final = Path(__file__).resolve().parents[2]
SCANNED: Final = ("app", "plugins", "config")
MARKER: Final = "TODO(user)"
MAX_ITEMS: Final = 200


class RuleBody(BaseModel):
    """A rule as the YAML holds it; the full validation is the startup one."""

    model_config = ConfigDict(extra="forbid")

    id: str
    applies_to: str
    check: str
    params: dict[str, Any] = {}
    severity: str
    source: dict[str, Any] | None = None


def _listing(request: Request, *, apply: bool = False) -> dict[str, Any]:
    rules, states = effective_rules(request.app.state.engine)
    if apply:
        # The next piece or placement check uses the table in force, with no restart.
        request.app.state.design_rules = rules
    return {
        "rules": [
            {"id": state.id, "origin": state.origin, "valid": state.valid, "problem": state.problem, **state.item}
            for state in states
        ],
        "checks": [{"name": name, "applies_to": check.applies_to} for name, check in sorted(CHECKS.items())],
    }


@router.get("/rules")
def list_rules(request: Request) -> dict[str, Any]:
    return _listing(request)


@router.put("/rules/{rule_id}")
def put_rule(rule_id: str, body: RuleBody, request: Request) -> dict[str, Any]:
    if body.id != rule_id:
        raise HTTPException(
            422,
            detail={"failure_class": "invalid_rule", "field": "id", "reason": "the id does not match the path"},
        )
    item = body.model_dump(exclude_none=True)
    try:
        save_override(request.app.state.engine, item)
    except DesignRulesError as error:
        reason = str(error)
        field = "source" if "source" in reason else "params" if "parameters" in reason else "rule"
        raise HTTPException(
            422,
            detail={"failure_class": "invalid_rule", "field": field, "reason": reason},
        ) from None
    return _listing(request, apply=True)


@router.delete("/rules/{rule_id}")
def reset_rule(rule_id: str, request: Request) -> dict[str, Any]:
    if not delete_override(request.app.state.engine, rule_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    return _listing(request, apply=True)


def open_items(root: Path = BACKEND) -> list[dict[str, Any]]:
    """Every `TODO(user)` in the backend code and configuration, tests and the virtualenv excluded."""
    found: list[dict[str, Any]] = []
    for folder in SCANNED:
        for path in sorted((root / folder).rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".yaml", ".yml", ".md", ".json"}:
                continue
            if "__pycache__" in path.parts or ".venv" in path.parts or "tests" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, start=1):
                if MARKER in line:
                    text = line.split(MARKER, 1)[1].lstrip(":) ").strip()
                    found.append({"file": str(path.relative_to(root)), "line": number, "text": text})
                    if len(found) >= MAX_ITEMS:
                        return found
    return found


@router.get("/open-items")
def list_open_items() -> list[dict[str, Any]]:
    return open_items()
