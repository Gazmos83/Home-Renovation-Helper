## 1. Settings and transport

- [x] 1.1 Add the `RENDER_OFFLOAD_*` settings (all-or-off, key and known-hosts readable, Blender path charset, device enum) and the startup summary line. Verify `tests/test_config.py` covers off when any value is missing, a missing key file failing startup by name, an invalid device or path refused, and no key path content in the summary
- [x] 1.2 Write `app/render/offload/transport.py` (ssh/scp argv builders over `Launch`, code-only remote command with `shlex.quote`). Verify `tests/test_offload_transport.py` covers the required `-o` options on every call, a 10 s connect timeout, quoting of every component, and a package id never appearing in a remote command

## 2. Generator flag and bundle

- [x] 2.1 Add `--cycles-device` (`CPU` default, `OPTIX|CUDA|HIP`) to `app/blender/cli.py` and `_render.py`, and define the generator bundle list. Verify a `--blender` test applies the render settings for each device value and reads `scene.cycles.device` without rendering, a `--blender` test runs the bundle copied to a temp folder with only Blender's Python (no render: `--help` path), and the existing `--blender` renders still pass at tier `draft`

## 3. Remote job

- [x] 3.1 Write `app/render/offload/check.py` (version probe, 60 s cache) and wire it ahead of `quote()` in the render tool and route for remote finals. Verify `tests/test_offload_check.py` (fake launcher) covers reachable 5.2.1 passing, unreachable / host-key failure / version 4.5 refused before approval with the owner-facing reason, and no local run started
- [x] 3.2 Write `app/render/offload/job.py` (mkdir, stale sweep, upload, run under remote `timeout`, copy back, local `viewer.html`, verify/publish reused, cleanup in `finally`) and dispatch to it from `run_render` for `target="remote"` under the server's own lock (`OffloadRuntime.semaphore`). Verify `tests/test_offload_job.py` with a fake transport at tier `final` covers success publishing 36 frames, a missing frame failing with nothing published, a timeout, cleanup on every path, no local fallback, a second remote final queued, and a local tier-`draft` render running concurrently with a remote final

## 4. Estimate, benchmark and records

- [x] 4.1 Add `target` to `RenderQuote`, the remote estimate formula and wording, the remote benchmark (guard-minted ticket, one Cycles frame at 1 MP on the server) and recalibration after the first remote final. Verify `tests/test_render_estimate.py` and `tests/test_benchmark.py` cover the spec's 36 × 2.25 × 0.2 + 40 example at tier `final`, a refusal without a remote benchmark, and the recalibration excluding transfer time
- [x] 4.2 Migration `0009_remote_render_jobs`, `target`/`transfer_seconds` in the render records and Langfuse event. Verify migration upgrade/downgrade, and `tests/test_render_logging.py` covering `target: local` on a tier-`draft` render and `target: remote` with transfer seconds on a tier-`final` remote job

## 5. Developer panel

- [x] 5.1 Add `app/api/admin_offload.py` (summary, connection test, run remote benchmark, target, hourly rate, recent jobs with euro estimate). Verify `tests/test_admin_offload_api.py` covers the target refused while unconfigured, the connection test result shape, 404 when the panel is disabled, and no host, target or euro figure in any homeowner route response
- [ ] 5.2 Add `frontend/src/routes/admin/Offload.tsx` and its admin route with Vitest coverage (refusal beside the target switch, job list). Verify `pnpm test` passes, then do a recorded browser check against a backend with offload unconfigured (refusal path) and with a fake configured summary

## 6. Verification

- [ ] 6.1 Manual check against a real rented GPU box when the owner has one running: connection test, remote benchmark, one approved tier-`final` still remotely. Record estimate vs actual in the commit message, or record that it was not run
- [x] 6.2 README (owner setup: rent a box, install Blender 5.2.1, keys, known_hosts, env values, switching the target) and CLAUDE.md §2 / §11 step 10 tick
- [x] 6.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, `uv run pytest --blender -m blender` (renders at tier `draft` only), and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
