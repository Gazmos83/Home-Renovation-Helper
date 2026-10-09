"""The checked-in design-rules table (`config/design_rules.yaml`) and its evaluation.

Each rule names a check from the closed set in `app.guidelines.checks`, its
parameters, a severity and the clause it is quoted from. Loading refuses an
unknown check, a missing or unknown source, or parameters the check does not
take, naming the rule id; the application loads the table at startup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from app.blender.custom_build.derive import BRACKET_COUNT_CHECK, BRACKET_SPACING_CHECK
from app.config import ConfigurationError
from app.guidelines.checks import CHECKS, Measurement
from app.guidelines.sources import source_ids

BRACKET_CHECKS: Final = (BRACKET_COUNT_CHECK, BRACKET_SPACING_CHECK)
DEFAULT_RULES_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "design_rules.yaml"
_OWNER_NOTE: Final = re.compile(r"^owner:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class DesignRulesError(ConfigurationError):
    """The rules table is unusable. The message names the rule id (or the file)."""


class RuleSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication: str
    section: str
    quote: str


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    applies_to: Literal["placement", "piece"]
    check: str
    params: dict[str, Any] = {}
    severity: Literal["warn", "refuse"]
    source: RuleSource | None = None


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    applies_to: str
    check: str
    params: BaseModel
    severity: str
    source: RuleSource


@dataclass(frozen=True, slots=True)
class Finding:
    rule: Rule
    measurement: Measurement

    def text(self) -> str:
        source = self.rule.source
        return (
            f"{self.rule.id}: {self.measurement.what} is {self.measurement.value}, limit "
            f"{self.measurement.limit} ({source.publication}, {source.section})"
        )


def load_rules(path: Path = DEFAULT_RULES_PATH, *, known_sources: frozenset[str] | None = None) -> tuple[Rule, ...]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DesignRulesError(f"design rules file not found: {path}") from None
    except yaml.YAMLError as error:
        raise DesignRulesError(f"design rules file is not valid YAML: {path}: {error}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("rules"), list):
        raise DesignRulesError(f"{path.name}: needs a 'rules' list")
    sources = source_ids() if known_sources is None else known_sources
    rules: list[Rule] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["rules"]):
        name = item.get("id") if isinstance(item, dict) else None
        label = name or f"#{index}"
        try:
            entry = RuleIn.model_validate(item)
        except ValidationError as error:
            raise DesignRulesError(f"rule {label!r}: {error.errors()[0]['msg']}") from None
        if entry.id in seen:
            raise DesignRulesError(f"rule {entry.id!r} is listed twice")
        seen.add(entry.id)
        source = entry.source
        if source is None or not (source.publication.strip() and source.section.strip() and source.quote.strip()):
            raise DesignRulesError(f"rule {entry.id!r} has no source: it needs a publication, a section and a quoted clause")
        if source.publication not in sources and not _OWNER_NOTE.match(source.publication):
            raise DesignRulesError(
                f"rule {entry.id!r}: source {source.publication!r} is neither in guideline_sources.yaml nor an owner note"
            )
        check = CHECKS.get(entry.check)
        if check is None:
            raise DesignRulesError(f"rule {entry.id!r}: unknown check {entry.check!r}")
        if check.applies_to != entry.applies_to:
            raise DesignRulesError(f"rule {entry.id!r}: check {entry.check!r} applies to a {check.applies_to}")
        try:
            params = check.params.model_validate(entry.params)
        except ValidationError as error:
            raise DesignRulesError(f"rule {entry.id!r}: parameters: {error.errors()[0]['msg']}") from None
        rules.append(Rule(entry.id, entry.applies_to, entry.check, params, entry.severity, source))
    for check in BRACKET_CHECKS:
        named = [rule.id for rule in rules if rule.check == check]
        if len(named) > 1:
            raise DesignRulesError(
                f"rules {named[0]!r} and {named[1]!r} both name {check!r}; the bracket calculator reads one"
            )
    return tuple(rules)


def evaluate(rules: tuple[Rule, ...], applies_to: str, subject: Any) -> list[Finding]:
    """Every breach of the rules for `applies_to` found in `subject`."""
    findings = []
    for rule in rules:
        if rule.applies_to != applies_to:
            continue
        for measurement in CHECKS[rule.check].run(subject, rule.params):
            if measurement.breached:
                findings.append(Finding(rule, measurement))
    return findings


def partition(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """(refusals, warnings)."""
    return (
        [f for f in findings if f.rule.severity == "refuse"],
        [f for f in findings if f.rule.severity == "warn"],
    )


def warnings_note(findings: list[Finding]) -> str:
    return "; ".join(f.text() for f in findings)



def refusal_text(refusals: list[Finding]) -> str:
    return "refused by a design rule: " + "; ".join(f.text() for f in refusals)


def piece_outcome(rules: tuple[Rule, ...], spec: Any) -> tuple[str | None, str]:
    """(a refusal, or `None`; the warnings to show the owner, or an empty string) for a piece."""
    refusals, warnings = partition(evaluate(rules, "piece", spec))
    return (refusal_text(refusals) if refusals else None), warnings_note(warnings)
