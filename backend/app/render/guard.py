"""The render guard (render-guard; CLAUDE.md §1, §6).

Nothing renders without passing through here. `authorise` validates the request,
computes and words the estimate, requires an explicit "yes" for the `final`
tier, and mints a `RenderTicket`. The runner launches a render process only for
a ticket it can consume: one this module minted, for that package/version/kind,
not yet used. A caller, a model or a spec cannot name a frame count, resolution
or engine — those come from the tier alone.

The guard is a plain function so it can be tested without Blender or a graph;
`guard_node` wraps it with LangGraph's `interrupt()` for agents.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from app.render.benchmark_store import Benchmark
from app.render.estimate import DEFAULT_CYCLES_MULTIPLIER, describe, estimate_seconds
from app.render.tiers import Tier, TierError, Tiers

# Request fields that would set a render parameter directly: always refused.
FORBIDDEN_FIELDS: Final[tuple[str, ...]] = (
    "frames",
    "resolution",
    "width",
    "height",
    "samples",
    "engine",
)
KINDS: Final[tuple[str, ...]] = ("still", "turntable")

_MINT: Final = object()


class RenderRefused(Exception):
    """The guard refused a render. `reason` is safe to show the owner."""

    def __init__(self, reason: str, *, failure_class: str = "refused", field: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.failure_class = failure_class
        self.field = field


class ApprovalRequired(RenderRefused):
    """A `final` render needs the owner's "yes" after seeing the estimate."""

    def __init__(self, quote: RenderQuote) -> None:
        super().__init__(
            f"a final render needs your approval: {quote.summary}",
            failure_class="approval_required",
        )
        self.quote = quote


class RenderNotAuthorised(Exception):
    """A render process was about to start without a valid guard ticket."""


@dataclass(frozen=True, slots=True)
class RenderQuote:
    """What a render would cost, shown before it runs."""

    package_id: str
    version: int
    kind: str
    room: bool
    tier: Tier
    frames: int
    estimate_seconds: float

    @property
    def estimate_text(self) -> str:
        return describe(self.estimate_seconds)

    @property
    def summary(self) -> str:
        what = "a still" if self.kind == "still" else f"{self.frames} frames"
        return (
            f"tier {self.tier.name} — {what} at {self.tier.resolution}×{self.tier.resolution} "
            f"on {self.tier.engine}, {self.estimate_text}"
        )


class RenderTicket:
    """Authorisation to launch exactly one render process.

    Only `authorise` can create one (the private mint token is checked), and it
    is single-use: `consume()` succeeds once.
    """

    __slots__ = ("_consumed", "quote")

    def __init__(self, quote: RenderQuote, *, _mint: object = None) -> None:
        if _mint is not _MINT:
            raise RenderNotAuthorised("a render ticket can only be issued by the render guard")
        self.quote = quote
        self._consumed = False

    @property
    def consumed(self) -> bool:
        return self._consumed

    def matches(self, package_id: str, version: int, kind: str, room: bool) -> bool:
        q = self.quote
        return (q.package_id, q.version, q.kind, q.room) == (package_id, version, kind, room)

    def consume(self) -> None:
        if self._consumed:
            raise RenderNotAuthorised("this render authorisation was already used")
        self._consumed = True


# The first-launch benchmark is the one render outside the tiers (CLAUDE.md §6):
# one Eevee frame at 1000 × 1000, run only on the owner's explicit request. It
# still needs a ticket, minted here and nowhere else.
BENCHMARK_TIER: Final = Tier(
    name="benchmark", frames=1, resolution=1000, engine="eevee", timeout_multiplier=1
)
BENCHMARK_PACKAGE_ID: Final = "benchmark"


def _is_yes(approval: object) -> bool:
    return isinstance(approval, str) and approval.strip().lower() == "yes"


def quote(
    *,
    package_id: str,
    version: int,
    kind: str,
    tier: object,
    tiers: Tiers,
    benchmark: Benchmark | None,
    cycles_multiplier: float = DEFAULT_CYCLES_MULTIPLIER,
    room: bool = False,
    raw_fields: Iterable[str] = (),
) -> RenderQuote:
    """Validate a request and price it. Never approves and never starts anything."""
    for name in raw_fields:
        if name in FORBIDDEN_FIELDS:
            raise RenderRefused(
                f"{name} cannot be set on a render; choose a tier "
                f"({', '.join(t for t, _ in tiers.items())}) and it decides frames, "
                "resolution and engine",
                field=name,
            )
    if tier is None or tier == "":
        raise RenderRefused("a tier is required: choose draft, preview or final", field="tier")
    try:
        chosen = tiers.get(tier)
    except TierError as error:
        raise RenderRefused(str(error), field="tier") from None
    if kind not in KINDS:
        raise RenderRefused(f"unknown render kind {kind!r}; use still or turntable", field="kind")
    if benchmark is None:
        raise RenderRefused(
            "no benchmark has been run yet; run the benchmark first so the estimate is real",
            failure_class="benchmark_missing",
        )
    frames = 1 if kind == "still" else chosen.frames
    seconds = estimate_seconds(
        chosen, benchmark.seconds_per_megapixel, cycles_multiplier, frames=frames
    )
    return RenderQuote(package_id, version, kind, room, chosen, frames, seconds)


def authorise(
    *,
    package_id: str,
    version: int,
    kind: str,
    tier: object,
    tiers: Tiers,
    benchmark: Benchmark | None,
    cycles_multiplier: float = DEFAULT_CYCLES_MULTIPLIER,
    room: bool = False,
    raw_fields: Iterable[str] = (),
    approval: object = None,
) -> RenderTicket:
    """Validate, price and — for `final` — require approval; then mint a ticket."""
    priced = quote(
        package_id=package_id,
        version=version,
        kind=kind,
        tier=tier,
        tiers=tiers,
        benchmark=benchmark,
        cycles_multiplier=cycles_multiplier,
        room=room,
        raw_fields=raw_fields,
    )
    if priced.tier.name == "final" and not _is_yes(approval):
        if approval is None:
            raise ApprovalRequired(priced)
        raise RenderRefused("the final render was not approved", failure_class="declined")
    return RenderTicket(priced, _mint=_MINT)


def authorise_benchmark() -> RenderTicket:
    """A ticket for the one-frame Eevee benchmark. The caller (an explicit owner
    request: the dev-gated route or the CLI) is the approval."""
    benchmark_quote = RenderQuote(
        package_id=BENCHMARK_PACKAGE_ID,
        version=1,
        kind="still",
        room=False,
        tier=BENCHMARK_TIER,
        frames=1,
        estimate_seconds=0.0,
    )
    return RenderTicket(benchmark_quote, _mint=_MINT)
