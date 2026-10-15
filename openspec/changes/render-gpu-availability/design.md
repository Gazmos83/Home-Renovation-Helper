## Context

See proposal.md for the motivation. What exists (from `render-pod-lifecycle`):

- **RunPod client.** `RunPodClient` in `app/render/offload/runpod.py` calls REST v1 at `https://rest.runpod.io/v1`. The key comes from `SecretStr` and is used only to build the header; there are no redirects and a 15 s timeout.
- **Pre-approval check.** `OffloadChecker.check_runpod(client, volume_id)` in `check.py` reads the network volume within the 10 s check limit and caches a pass for 60 s. `ensure_server` calls it in pod mode when no pod is running.
- **Pod sessions.** `render_pod_sessions` holds `created_at`, `ready_at`, `deleted_at`, `gpu_type` (the placed type), `jobs` and `outcome` (`start_failed` among others). `sessions.recent_sessions` feeds the panel.
- **Settings.** Operator settings are read through `benchmark_store` (`offload:idle_minutes`, `offload:boot_seconds`).

**RunPod catalog (checked 2026-10-15).** The v2 server is `https://api.runpod.io` (from `https://api.runpod.io/v2/openapi.json`). `GET /v2/catalog/gpus` with `include=AVAILABILITY&product=POD&cloud=SECURE` returns every GPU type with an overall `availability`. It also returns `dataCenters: [{id, availability}]`, listing only data centres where that type has stock. Levels are `NONE`, `LOW`, `MEDIUM`, `HIGH`. Read live that day: the RTX 4090 listed EU-RO-1 in the morning and did not list it in the afternoon.

## Goals / Non-Goals

**Goals:**
- A final that cannot start for lack of stock is refused in seconds, before approval, and nothing is billed.
- After a week or two, the owner can read from the panel how often a render GPU was available and how often starts succeeded.

**Non-Goals:**
- Choosing another data centre, or creating volumes elsewhere. That is deferred until the history exists.
- Predicting stock, or alerting on it.
- Treating stock as a guarantee. A type listed `LOW` can still fail to place, so the create stays the authority.

## Decisions

1. **One v2 catalog read, in the existing client.** `RunPodClient.gpu_stock(gpu_types, data_center) -> dict[str, str]` makes one `GET https://api.runpod.io/v2/catalog/gpus` with the three query values. It uses the same Bearer key and the same no-redirect, timeout and error mapping as the v1 calls. The base URL is a second constant beside `RUNPOD_API`. For each configured type, the level is the `availability` of its entry for that data centre, or `NONE` when the type or the data centre is not listed. Unknown level strings count as `NONE`. *Alternative:* one `GET /v2/catalog/gpus/{id}` per type. Rejected: three to five calls for the same answer. *Alternative:* `GET /v2/catalog/datacenters/{id}?include=GPU_AVAILABILITY`. Rejected because it takes no `product` filter, and RunPod says stock differs by product. Live read 2026-10-15 16:4x UTC with the app's own key: `200`, body `{"gpus": [...]}`. RTX 4090 `LOW` with `dataCenters: [{"availability": "LOW", "id": "EU-RO-1", "name": "EU-RO-1"}]`; RTX 5090 `LOW` with `dataCenters: null`; RTX A4500 `NONE` with `dataCenters: null` (one A4500 was in use by the app's pod at the time). So `dataCenters` can be `null` even when the overall level is not `NONE`, and the per-data-centre entry is what counts.

2. **The stock check sits inside `check_runpod`.** After the volume read (which already gives the data centre), the check reads stock with the time left of the 10 s limit. If all types are `NONE`, it raises `RenderRefused` with `failure_class="offload_no_stock"`. A `RunPodError` or a timeout on the stock read is logged (`offload.stock_unread`) and does not refuse. A pass is cached for 60 s as now, so a quote followed by an approval does not read stock twice. Stock is not read when a pod is running (the check uses SSH then).

3. **Sampler as one loop task.** `availability.StockSampler` is started in the lifespan only in pod mode, on the app loop, and cancelled at shutdown.
   - Every 900 s it reads `offload:stock_sampling` (absent means on). If sampling is on, it reads the volume's data centre and the stock, and inserts one `gpu_stock_samples` row per configured type, all with the same `taken_at`. The volume's data centre is cached for an hour, since a volume does not move.
   - Each sample also deletes rows older than 90 days. That is one indexed `DELETE`, simpler than a separate daily job.
   - Any failure is logged and the loop goes on.
   - Tests inject the clock, the sleep and the client.

   *Alternative:* a cron job outside the app. Rejected: the app already owns the key and the loop, and a second process would need the secret too.

4. **Table `gpu_stock_samples`.** Migration `0026_gpu_stock_samples`, revising `0025_relabel_preview_tier`, the current single head. Columns: `id`, `taken_at` (timestamptz, indexed), `data_center` (String 32), `gpu_type` (String 100), `availability` (String 8, check constraint on the four levels). About 96 × 3 rows a day, under 30,000 at the 90-day cap.

5. **History computed on read.** `availability.history(session, days)` returns `{starts, started_share, median_startup_seconds, placed: {type: n}, failed_starts, samples, any_in_stock_share, per_type_share: {type: share}, last_sample_at}`.
   - Starts are sessions created in the window, except `orphaned` ones, which were not this run's starts.
   - "Started" means `ready_at` is set. The median is over `ready_at − created_at`.
   - A sample time is a distinct `taken_at`. It counts as in stock when any of its rows is not `NONE`.
   - Shares are `None` when their count is zero, so the panel says "none yet".

6. **API and panel.** `GET /admin/offload` gains `availability: {"7": …, "30": …}` and `stock_sampling: bool`, in pod mode only. `PUT /admin/offload/sampling {on: bool}` writes the setting. The Render Offload tab adds an "Availability" section with the two periods side by side and the switch. No homeowner route reads any of it. The homeowner sees only the refusal reason, which names GPU types and a data centre, not a host, cost or account detail.

## Risks / Trade-offs

- **Snapshot vs reality** → `LOW` can still fail to place, and a type can come back between the check and the approval. The create remains the authority. The check only removes the certain refusals.
- **Sampling bias** → A 15-minute grid can miss short windows of stock. That is good enough to compare "often" and "rarely". The sample count is shown, so a thin history is visible.
- **v2 key scope** → If the app's key cannot read v2, the stock read fails. The check then passes, and sampling stores nothing and logs it. Task 1.1 confirms the key works on v2 before building on it.
- **Migration order** → `0026` assumes `two-tier-renders` lands first with `0025`. If the order changes, renumber before applying.

## Migration Plan

Deploy after `render-pod-lifecycle` is archived and migration `0025` exists. The migration is additive, and sampling starts at the next startup in pod mode. Rollback: switch sampling off, or downgrade `0026`. The pre-approval stock check is removed by reverting the code; there is no data to undo.
