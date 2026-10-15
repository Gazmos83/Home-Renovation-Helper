## 1. Settings and RunPod client

- [x] 1.1 Add `RENDER_OFFLOAD_RUNPOD_API_KEY` (`SecretStr`), `_NETWORK_VOLUME_ID`, `_GPU_TYPE` and `_IMAGE` to `app/config.py`, with plain-identifier validation and a pinned image tag. Add a `render_offload_mode` property (`off` / `host` / `pod`) and a startup failure when both a host and the RunPod key are set. Verify with config tests for each mode, the conflict, and a startup summary that never contains the key.
- [x] 1.2 Confirm against the live RunPod API reference that network volumes require `cloudType="SECURE"` and whether `dataCenterIds` must be passed with `networkVolumeId`. Record the answer in design.md decision 3 and verify that the pod-body test asserts it.
- [x] 1.3 Add `app/render/offload/runpod.py` (design decision 2) with `create_pod`, `get_pod`, `delete_pod`, `list_pods` and `get_network_volume`, a fixed base URL and no redirects. Verify with `httpx.MockTransport` tests for each call: the request body built only from constants and settings, 401 / 404 / capacity / other errors mapped to safe reasons, and the key absent from every error and log line.

## 2. Pod lifecycle

- [x] 2.1 Add `HostKeyAlias` support and a per-pod host and port to `OffloadConfig` and `transport.py`, leaving fixed-host argv unchanged. Verify with argv tests for both modes.
- [x] 2.2 Add migration `0024_render_pod_sessions` and a small store for sessions and `offload:idle_minutes` / `offload:boot_seconds`. Verify with `uv run alembic upgrade head` and store tests (idle default 10, range 1–120).
- [x] 2.3 Add `app/render/offload/pod.py` `PodManager.ensure_pod()`: reuse a running pod, or create one, poll for address and port, retry the SSH version check until it passes or 10 minutes pass, and store the start-up time. On failure, delete the pod and raise `RemoteFailed` with the reason. Verify with fake RunPod and fake `Launch` tests: first start, reuse, no GPU free, start-up timeout (pod deleted), and wrong host key.
- [x] 2.4 Add the idle timer: `job_finished()` sets the deadline, one loop task deletes the pod only when the offload semaphore is free, and a job during idle time postpones deletion. Retry a failed delete every minute and record each session's outcome. Verify with a fake clock: deletion at end + idle, postponement, no deletion during a job, and the delete-failure retry.
- [x] 2.5 Wire `ensure_pod()` / `job_finished()` into `app/blender/runner.py` (inside `offload.semaphore`, before `on_start`) and `app/render/offload/benchmark.py`. Verify with runner tests: a remote `final`-tier job on a fake pod publishes as before, calibration excludes start-up, and a start-up failure records the job failed with no local run.
- [x] 2.6 Add lifespan startup cleanup (delete `hra-render` pods, record them as orphaned, leave other pods alone) and shutdown delete (30 s cap) in `app/main.py`. Verify with lifespan tests against a fake client.

## 3. Check and estimate

- [x] 3.1 Branch `OffloadChecker.check` for pod mode: SSH check when a pod is running, `get_network_volume` when not, never creating a pod. Verify with tests: pod mode with nothing running passes without a create call, 401 refuses before approval with the key-rejected reason, and the existing fixed-host check tests are unchanged.
- [x] 3.2 Add start-up seconds to the remote estimate when the mode is pod and no pod is running (180 s default), through `remote_benchmark_for` callers in `app/api/renders.py`, `plugins/render_turntable/tool.py` and `plugins/photoreal_detail/tool.py`. Verify with estimate tests: 56 s with a running pod and 206 s with a 150 s start-up, both for a `final`-tier turntable, and the homeowner wording carrying no host or cost.

## 4. Developer panel

- [x] 4.1 Extend `app/api/admin_offload.py`: the mode summary (no key shown); the pod-mode connection test without creating a pod; pod state; `POST /pod/delete` (refused while a job runs); `PUT /idle` (1–120); and the last twenty pod sessions with cost. Verify with route tests behind the developer gate, including the delete refusal and the idle range.
- [x] 4.2 Extend `frontend/src/routes/admin/Offload.tsx` with the mode, the pod state with deletion time, "Delete pod now", the idle-minutes field and the pod-sessions table. Verify with Vitest tests, `pnpm lint` and `pnpm build`.
- [x] 4.3 Browser pass of the Render Offload tab in pod mode against a faked backend state (state none, running, delete failed). Verify with recorded screenshots.
  Browser pass 2026-10-15: headless Chromium through Python Playwright 1.63, scratch database `home_renovation_pod_ui` (dropped afterwards), backend on 8100 (developer panel on, gateway probe off, offload off) and the `vite build` served by `vite preview` on 5200 (`API_PROXY`); the owner's 8000 and 5173 were untouched. The `/admin/offload*` responses were faked in the browser (pod states none, running and delete failed), so nothing reached RunPod. 15 checks passed: pod settings shown and no key on the page; "No pod running … 10 idle minutes" with "Delete pod now" disabled; the connection test says no pod was started; idle 0 refused next to the field, 15 saved; running shows "deleted at 14:10 UTC if still idle"; "Delete pod now" returns to none; a failed delete shows its error and the retry note; a session row shows "30 min 0 s" and "$0.35"; no horizontal page scroll at 420 px (the sessions table scrolls inside its own frame, like the jobs table); no page errors; no request outside localhost. Screenshots in the session scratchpad (`pod-ui/1-none.png` … `4-phone.png`).

## 5. Owner setup and docs

- [x] 5.1 Add `scripts/runpod/setup_volume.sh` and `docs/runpod-setup.md` (design decision 10): Blender 5.2.1 download with SHA-256 check, host key and authorised key on the volume, and the known-hosts alias line. Verify the script with `bash -n` and `shellcheck`, and that the guide covers choosing a data centre with stock of the GPU.
- [x] 5.2 Update CLAUDE.md §2 "Render server" and §6, and README offload setup, to say a RunPod pod is created after approval and deleted after the idle time. Verify by review that fixed-host mode is still described.
- [x] 5.3 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, and `pnpm test` in `frontend/`. Verify that all pass.
  Run 2026-10-15: `ruff check .` clean; `pytest -m "not slow"` 2614 passed, 42 skipped, 2 failed. `test_engineering_registry.py` pinned the head revision to `0023`; it is updated to `0024_render_pod_sessions`, as each earlier migration did, and that file now passes. `test_kitchen_engineering.py::test_seed_links_registers_kitchen_sources_without_chunks` passes on its own: it counts newly seeded catalogue rows, so it depends on what other tests left in the shared database, and is unrelated to this change. `pnpm test`: 411 passed; `pnpm lint` and `pnpm build` clean.
- [ ] 5.4 Owner-run live check (needs the owner's RunPod account): run the connection test, then the remote benchmark (pod created, start-up time stored), then one approved `final`-tier turntable. Confirm the pod is deleted 10 minutes later and the session's cost is shown. Verify with the developer panel's pod-sessions row and the RunPod console showing no pod.

## 6. GPU priority list (after the first live run)

- [x] 6.1 Accept up to five comma-separated GPU types in `RENDER_OFFLOAD_RUNPOD_GPU_TYPE`, each validated; summarise them in order. Verify with config tests (one type, three types, six refused, an unsafe entry refused).
- [x] 6.2 Send the list as `gpuTypeIds` with `gpuTypePriority="custom"`, name all types in the no-capacity reason, recognise RunPod's "no instances currently available" wording, and record the type the pod got in its session. Verify with RunPod-client and pod-manager tests, including first choice sold out.
- [x] 6.3 Show the GPU types in order on the Render Offload tab and the GPU each session got. Verify with Vitest, `pnpm lint` and `pnpm build`.

## 7. Early give-up and visible errors (after the second live run)

- [x] 7.1 Fail the start after 3 minutes when RunPod has given the pod no address and SSH port, delete the pod and record `start_failed`. Verify with a pod-manager test that fails at 3 minutes, and that a pod with an address still gets the full 10 minutes.
- [x] 7.2 Give `/admin/offload` the same no-timeout proxy settings as `/chat` in `vite.config.ts`, and show "the server answered <status>" when an error carries no reason. Verify with a Vitest case for an empty error body, `pnpm lint` and `pnpm build`.
