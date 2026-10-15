"""Run a batch of restyle turntables (restyle-variants; two-tier-renders).

One guard ticket per variant, issued together after one batch estimate. Each variant is a
headless Blender process under the one-process rule: the built version is opened (or the
composition rebuilt), the look or style applied in memory, a draft turntable rendered with
its first frame as the variant's `still.png`, and nothing saved. A variant that fails is
reported by id and the finished ones stay published. Each variant's own outcome goes to
`on_variant`, which finishes its render run.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from app.blender import storage
from app.blender.launch import Launch, subprocess_launch
from app.blender.runner import RESTYLE_RENDERER, launch_guarded, safe_error
from app.blender.verify import VerificationError, verify_frames, verify_png
from app.observability.langfuse import Tracing
from app.render.guard import RenderNotAuthorised, RenderTicket
from app.render.records import log_render_finished, log_render_started
from app.restyle import store
from app.restyle.presets import APPEARANCE_NOTE
from app.restyle.request import VariantPlan

logger = logging.getLogger("app")


@dataclass(frozen=True, slots=True)
class RestyleJob:
    ticket: RenderTicket
    plan: VariantPlan
    variant_id: str
    # The variant's render run (a piece's variant is rateable); `None` when none was recorded.
    run_id: UUID | None = None


@dataclass(slots=True)
class VariantOutcome:
    variant_id: str
    label: str
    error: str | None = None


@dataclass(slots=True)
class RestyleResult:
    outcomes: list[VariantOutcome] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[VariantOutcome]:
        return [outcome for outcome in self.outcomes if outcome.error]

    @property
    def outcome(self) -> str:
        return "succeeded" if not self.failed else "failed"


def _argv(job: RestyleJob, *, folder: Path, root: Path, blender_bin: Path, stage: Path,
          payload: Path, models_root: Path) -> list[str]:
    tier = job.ticket.quote.tier
    argv = [str(blender_bin), "--background", "--python", str(RESTYLE_RENDERER), "--",
            "--restyle", str(payload), "--out", str(stage)]
    if job.plan.kind == "room":
        argv += ["--spec", str(folder / storage.INPUT_FILE), "--pieces", str(root), "--models", str(models_root)]
    else:
        argv += ["--blend", str(folder / "model.blend")]
    return argv + ["--tier-frames", str(tier.frames), "--tier-resolution", str(tier.resolution),
                   "--tier-engine", tier.blender_engine]


async def run_restyle(
    jobs: list[RestyleJob],
    *,
    root: Path,
    blender_bin: Path,
    timeout: float,
    semaphore: asyncio.Semaphore,
    launch: Launch = subprocess_launch,
    models_root: Path | None = None,
    tracing: Tracing | None = None,
    on_outcome: Callable[[str], None] | None = None,
    on_variant: Callable[[RestyleJob, str], None] | None = None,
) -> RestyleResult:
    """Render each job in turn; never raises (a failure is recorded in the result)."""
    result = RestyleResult()
    if not jobs:
        return result
    first = jobs[0].ticket.quote
    folder = storage.record_version_dir(root, first.record, first.package_id, first.version)
    variants = store.variants_dir(folder)
    variants.mkdir(exist_ok=True)
    store.sweep_stale(folder)
    for job in jobs:
        quote = job.ticket.quote
        stage = store.stage_path(folder, job.variant_id)
        payload = variants / f".{job.variant_id}.restyle.json"
        error: str | None = None
        actual = 0.0
        try:
            payload.write_text(json.dumps(job.plan.payload), encoding="utf-8")
            argv = _argv(
                job, folder=folder, root=root, blender_bin=blender_bin, stage=stage, payload=payload,
                models_root=models_root or root / "models",
            )
            started = {"t": 0.0}

            async def starting(args: list[str], cwd: Path, seconds: float, _s=started, _q=quote) -> object:
                _s["t"] = time.perf_counter()
                log_render_started(_q, tracing=tracing)
                return await launch(args, cwd, seconds)

            expected = (
                quote.package_id, quote.version, quote.kind, quote.room, quote.record, quote.source,
                job.variant_id,
            )
            outcome = await launch_guarded(
                job.ticket, expected=expected, argv=argv, cwd=folder,
                timeout=timeout * quote.tier.timeout_multiplier, semaphore=semaphore, launch=starting,
            )
            actual = time.perf_counter() - started["t"] if started["t"] else 0.0
            if outcome.exit_code != 0 or outcome.timed_out:
                error = safe_error(outcome.stderr_tail, root)
            else:
                verify_frames(stage, quote.frames, quote.tier.resolution)
                verify_png(stage / "still.png", (quote.tier.resolution, quote.tier.resolution))
                result.replaced += store.make_room(folder, 1)
                store.publish(
                    folder, job.variant_id, stage,
                    {
                        "source": "restyle", "variant": job.variant_id, "label": job.plan.label,
                        "tier": quote.tier.name, "version": quote.version, "note": APPEARANCE_NOTE,
                        "estimate_seconds": round(quote.estimate_seconds, 3),
                        "actual_seconds": round(actual, 3), **job.plan.record,
                    },
                )
        except RenderNotAuthorised as refusal:
            error = safe_error(str(refusal), root)
        except (VerificationError, OSError, ValueError) as problem:
            error = safe_error(f"publish: {problem}", root)
        except Exception as problem:  # noqa: BLE001 - a background job must record, not raise
            error = safe_error(f"restyle: {type(problem).__name__}: {problem}", root)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            payload.unlink(missing_ok=True)
        log_render_finished(
            quote, actual_seconds=actual, outcome="failed" if error else "succeeded", error=error,
            tracing=tracing,
        )
        result.outcomes.append(VariantOutcome(job.variant_id, job.plan.label, error))
        if on_variant is not None:
            try:
                on_variant(job, "failed" if error else "succeeded")
            except Exception:  # noqa: BLE001 - a finished variant must stay finished
                logger.warning("restyle.variant_callback_failed")
    if on_outcome is not None:
        try:
            on_outcome(result.outcome)
        except Exception:  # noqa: BLE001 - a finished render must stay finished
            logger.warning("restyle.outcome_callback_failed")
    return result
