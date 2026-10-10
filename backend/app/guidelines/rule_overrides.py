"""Design rules edited from the developer panel, stored over the checked-in table (dev-panel-insights).

`config/design_rules.yaml` stays the shipped table and is never rewritten. A rule
added or edited on the panel is stored in `operator_settings` under
`design_rule:<id>` as the same JSON a YAML entry holds. The table in force is the
file's rules with each stored rule replacing the one of the same id, or added when
the id is new, validated exactly as startup validates the file. A stored rule
whose owner note is gone, or that no longer validates, is skipped and reported by
name; it never stops the service.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import GuidelineNote, OperatorSetting
from app.guidelines.rules import DEFAULT_RULES_PATH, DesignRulesError, Rule, parse_rules
from app.guidelines.sources import source_ids

PREFIX: Final = "design_rule:"
RULE_ID: Final = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,50}[a-z0-9])?$")


@dataclass(frozen=True)
class RuleState:
    """One rule as the panel lists it: its JSON, where it comes from, and whether it is in force."""

    id: str
    item: dict[str, Any]
    origin: str  # "file", "edited" (a file rule changed on the panel) or "panel"
    valid: bool
    problem: str | None = None


def file_items(path: Path = DEFAULT_RULES_PATH) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [dict(item) for item in raw["rules"]]


def read_overrides(engine: Engine) -> dict[str, dict[str, Any]]:
    with Session(engine) as session:
        rows = session.scalars(select(OperatorSetting).where(OperatorSetting.key.startswith(PREFIX))).all()
        return {row.key.removeprefix(PREFIX): json.loads(row.value) for row in rows}


def _owner_notes(engine: Engine) -> frozenset[str]:
    with Session(engine) as session:
        return frozenset(f"owner:{note_id}" for note_id in session.scalars(select(GuidelineNote.id)))


def _missing_note(item: dict[str, Any], notes: frozenset[str]) -> str | None:
    publication = str((item.get("source") or {}).get("publication", ""))
    if publication.startswith("owner:") and publication not in notes:
        return f"rule {item.get('id')!r}: source {publication!r} names an owner note that does not exist"
    return None


def _merged(items: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    found = [existing for existing in items if existing.get("id") != item.get("id")]
    replaced = len(found) != len(items)
    if not replaced:
        return [*items, item]
    return [item if existing.get("id") == item.get("id") else existing for existing in items]


def effective_rules(
    engine: Engine, path: Path = DEFAULT_RULES_PATH, *, known_sources: frozenset[str] | None = None
) -> tuple[tuple[Rule, ...], list[RuleState]]:
    """The rules in force and every rule's state, file and panel alike."""
    sources = source_ids() if known_sources is None else known_sources
    items = file_items(path)
    file_ids = {item["id"] for item in items}
    notes = _owner_notes(engine)
    states: dict[str, RuleState] = {item["id"]: RuleState(item["id"], item, "file", True) for item in items}
    for rule_id, item in sorted(read_overrides(engine).items()):
        origin = "edited" if rule_id in file_ids else "panel"
        problem = _missing_note(item, notes)
        if problem is None:
            try:
                parse_rules(_merged(items, item), sources)
            except DesignRulesError as error:
                problem = str(error)
        if problem is not None:
            states[rule_id] = RuleState(rule_id, item, origin, False, problem)
            continue
        items = _merged(items, item)
        states[rule_id] = RuleState(rule_id, item, origin, True)
    return parse_rules(items, sources), list(states.values())


def save_override(
    engine: Engine, item: dict[str, Any], path: Path = DEFAULT_RULES_PATH, *, known_sources: frozenset[str] | None = None
) -> tuple[Rule, ...]:
    """Store a rule after validating the table it would make; raises `DesignRulesError` naming the rule."""
    rule_id = str(item.get("id", ""))
    if not RULE_ID.match(rule_id):
        raise DesignRulesError(f"rule {rule_id!r}: id must be lowercase letters, digits and hyphens, at most 52")
    problem = _missing_note(item, _owner_notes(engine))
    if problem:
        raise DesignRulesError(problem)
    _rules, states = effective_rules(engine, path, known_sources=known_sources)
    items = file_items(path)
    for state in states:
        if state.valid and state.origin != "file":
            items = _merged(items, state.item)
    sources = source_ids() if known_sources is None else known_sources
    parse_rules(_merged(items, item), sources)
    with Session(engine) as session:
        key = PREFIX + rule_id
        row = session.get(OperatorSetting, key)
        value = json.dumps(item, sort_keys=True)
        now = datetime.now(UTC)
        if row is None:
            session.add(OperatorSetting(key=key, value=value, updated_at=now))
        else:
            row.value, row.updated_at = value, now
        session.commit()
    return effective_rules(engine, path, known_sources=known_sources)[0]


def delete_override(engine: Engine, rule_id: str) -> bool:
    """Reset an edited file rule to the file, or delete a panel rule; `False` when nothing was stored."""
    with Session(engine) as session:
        row = session.get(OperatorSetting, PREFIX + rule_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True

