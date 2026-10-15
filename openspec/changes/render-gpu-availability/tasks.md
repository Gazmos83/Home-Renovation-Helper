## 1. Stock read

- [x] 1.1 Confirm with one live read that the app's RunPod API key can call `GET https://api.runpod.io/v2/catalog/gpus?include=AVAILABILITY&product=POD&cloud=SECURE`, and record the response shape for the configured types in design.md. Verify by noting the date and the levels read.
- [x] 1.2 Add `RunPodClient.gpu_stock(gpu_types, data_center)` (design decision 1). Verify with `httpx.MockTransport` tests: a type listed `LOW` in the data centre, a type listed only elsewhere (`NONE`), a type missing from the catalog (`NONE`), an unknown level (`NONE`), the query values sent, 401/500/timeout mapped to `RunPodError`, and the key absent from errors.

## 2. Check before approval

- [x] 2.1 Read stock in `check_runpod` after the volume, refuse with `offload_no_stock` when every type is `NONE`, and pass when the stock read fails (design decision 2). Verify with check tests for the four scenarios in the render-offload delta: nothing in stock, one type in stock, stock read fails, pod running.
- [x] 2.2 Show the refusal through the render route and both render tools unchanged. Verify with a wiring test that a `final`-tier turntable is refused before approval with the GPU types and data centre named, and nothing is created.

## 3. Sampling

- [x] 3.1 Add migration `0026_gpu_stock_samples` and the model (design decision 4). Verify with `uv run alembic upgrade head`, a downgrade/upgrade drift test, and `tests/test_engineering_registry.py`'s head pin updated.
- [x] 3.2 Add `availability.StockSampler` (design decision 3) with an injected clock, sleep and client, and the `offload:stock_sampling` setting (on when absent). Verify with tests: one sample stores one row per type with `NONE` for unlisted types, sampling off stores nothing, a failed read stores nothing and the next interval samples, and rows older than 90 days are pruned.
- [x] 3.3 Start the sampler in the lifespan in pod mode only and cancel it at shutdown. Verify with a startup test against the fake RunPod: no sampler when offload is off or in host mode.

## 4. History and panel

- [x] 4.1 Add `availability.history(session, days)` (design decision 5). Verify with tests for the dev-panel scenarios: 4 starts / 75% / 90 s median / 1 failed, 62 of 100 samples in stock, no samples yet, and orphaned sessions not counted.
- [x] 4.2 Extend `GET /admin/offload` with `availability` and `stock_sampling`, and add `PUT /admin/offload/sampling`. Verify with route tests behind the developer gate, including a homeowner route that carries none of it.
- [x] 4.3 Add the Availability section and the sampling switch to the Render Offload tab. Verify with Vitest cases (both periods, none yet, the switch), `pnpm lint` and `pnpm build`.
- [x] 4.4 Browser pass of the Availability section against faked responses at 1280 px and 420 px. Verify with recorded screenshots and no horizontal page scroll.
  Browser pass 2026-10-15: headless Chromium through Python Playwright 1.63, scratch database `home_renovation_avail_ui` (dropped afterwards), backend on 8100 with offload off and a `vite build` served by `vite preview` on 5200; the owner's 8000 and 5173 were untouched. `/admin/offload*` was faked in the browser (pod mode, a 7-day period with figures and an empty 30-day period). 11 checks passed: both periods' lines and the per-type shares, "No pod starts yet." and "No stock samples yet." for 30 days, the switch shows on, saves off and stays off after a reload, no horizontal page scroll at 420 px, no page errors, no request outside localhost. Screenshots in the session scratchpad (`avail-ui/`).

## 5. Docs and checks

- [x] 5.1 Add a paragraph to `docs/runpod-setup.md` on the stock refusal and reading the availability history. Verify by review.
- [x] 5.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm test`, `pnpm lint` and `pnpm build`. Verify that all pass, and record any failure that belongs to another change.
  Run 2026-10-15: `ruff check .` clean; `pytest -m "not slow"` 2674 passed, 42 skipped, 1 failed: `test_kitchen_engineering.py::test_seed_links_registers_kitchen_sources_without_chunks`, the same order-dependent test as in `render-pod-lifecycle` 5.3 (it passes on its own and is unrelated). `pnpm test` 425 passed; `pnpm lint` and `pnpm build` clean.
