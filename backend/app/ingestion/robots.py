"""Published crawling rules: fetch, parse, and decide.

`urllib.robotparser` is not usable here. It matches rule paths with a plain
prefix comparison, so a pattern like toom's `Disallow: /*?SID=` never matches
and the crawler would happily fetch a URL the site excluded. This module
implements the widely-observed extension instead: `*` matches any run of
characters, a trailing `$` anchors the end, and where several rules match a
path the longest pattern wins, with Allow beating Disallow on a tie.

Rules are data published by a third party. Nothing here executes or trusts
them beyond deciding whether a URL may be fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit

# Requesting rules must never look different from requesting a page: a site
# that refuses the honest identifier is refusing us, and that is the answer.
RULES_PATH: Final = "/robots.txt"


class RulesUnavailable(Exception):
    """The source did not serve its rules, so no permission has been granted.

    Carries the source and what came back, because the README has to record
    per-site review outcomes and "it refused" is a finding, not a crash.
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"{source} did not serve {RULES_PATH}: {reason}")


def _to_pattern(raw: str) -> re.Pattern[str]:
    anchored = raw.endswith("$")
    body = raw[:-1] if anchored else raw
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile(f"^{regex}{'$' if anchored else ''}")


@dataclass(frozen=True)
class Rule:
    allow: bool
    raw: str
    pattern: re.Pattern[str] = field(compare=False)

    @property
    def specificity(self) -> int:
        return len(self.raw)


@dataclass
class RobotsRules:
    """The rules that apply to one crawler identity."""

    rules: tuple[Rule, ...] = ()
    sitemaps: tuple[str, ...] = ()

    def allows(self, url: str) -> bool:
        """Whether these rules permit fetching `url`."""
        target = urlsplit(url)
        path = target.path or "/"
        if target.query:
            path = f"{path}?{target.query}"

        best: Rule | None = None
        for rule in self.rules:
            if not rule.pattern.match(path):
                continue
            if best is None or rule.specificity > best.specificity:
                best = rule
            elif rule.specificity == best.specificity and rule.allow:
                # A tie between Allow and Disallow resolves in favour of Allow.
                best = rule
        # Silence is permission: a path no rule names may be fetched.
        return True if best is None else best.allow

    def excluded(self, urls: list[str]) -> list[str]:
        return [url for url in urls if not self.allows(url)]


def parse_rules(text: str, *, user_agent: str) -> RobotsRules:
    """Parse robots.txt, keeping the group that applies to `user_agent`.

    A group naming our token exactly wins over the `*` group; if neither is
    present, no rule applies and everything is permitted.
    """
    token = user_agent.split("/")[0].strip().lower()

    groups: dict[str, list[Rule]] = {}
    sitemaps: list[str] = []
    current: list[str] = []
    previous_was_agent = False

    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()

        if field_name == "user-agent":
            if not previous_was_agent:
                current = []
            current.append(value.lower())
            groups.setdefault(value.lower(), [])
            previous_was_agent = True
            continue

        previous_was_agent = False

        if field_name == "sitemap" and value:
            sitemaps.append(value)
        elif field_name in {"allow", "disallow"} and current:
            # An empty Disallow means "nothing is disallowed"; it carries no
            # pattern, so it is simply not a rule.
            if not value:
                continue
            rule = Rule(field_name == "allow", value, _to_pattern(value))
            for agent in current:
                groups.setdefault(agent, []).append(rule)

    applicable = groups.get(token) or groups.get("*") or []
    return RobotsRules(rules=tuple(applicable), sitemaps=tuple(sitemaps))
