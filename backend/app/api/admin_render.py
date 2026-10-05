"""The developer-gated render benchmark routes (render-guard design decision 3).

`POST` measures and stores the benchmark (one Eevee frame of the reference
package); `GET` reads it. The panel must be enabled and the owner signed in:
with the panel off these answer 404, so the homeowner surface shows no sign of
them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.gate import require_dev
from app.api.packages import launcher, refused, require_generation
from app.render import benchmark_store
from app.render.benchmark import BenchmarkFailed, run_benchmark

router = APIRouter(
    prefix="/admin/render", tags=["admin"], dependencies=[Depends(require_dev)]
)


def _read(request: Request) -> dict:
    engine = request.app.state.engine
    found = benchmark_store.read_benchmark(engine)
    return {
        "benchmark": None
        if found is None
        else {
            "seconds_per_megapixel": found.seconds_per_megapixel,
            "measured_at": found.measured_at,
            "blender_version": found.blender_version,
        },
        "cycles_multiplier": benchmark_store.read_cycles_multiplier(engine),
        "cycles_calibrated": benchmark_store.stored_cycles_multiplier(engine) is not None,
    }


@router.get("/benchmark")
def read_benchmark(request: Request) -> dict:
    return _read(request)


@router.post("/benchmark", status_code=status.HTTP_200_OK)
async def run_the_benchmark(request: Request) -> dict:
    require_generation(request)
    settings = request.app.state.settings
    try:
        await run_benchmark(
            request.app.state.engine,
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            semaphore=request.app.state.blender_semaphore,
            launch=launcher(request),
        )
    except BenchmarkFailed as error:
        raise refused(status.HTTP_502_BAD_GATEWAY, "benchmark_failed", str(error)) from None
    return _read(request)
