## Why

In pod mode a render pod can only start in the network volume's data centre (EU-RO-1). On 2026-10-15 the RTX 4090 and then the RTX A4500 sold out there within hours, and one pod was placed but never started. Today the owner only finds out after approving a final and waiting. Runpod publishes a live stock level per GPU and data centre, but no history. The owner asked (2026-10-15) for:
1. a stock check before approval, so a final that cannot start is refused at once;
2. an availability history on the developer panel, to see how often a render GPU is actually available before deciding on more data centres.

## What Changes

- **Stock check before approval.** In pod mode with no pod running, the existing pre-approval check also reads Runpod's live pod stock for the configured GPU types in the volume's data centre. If every type reads `NONE` there, the final is refused before approval, naming the GPU types and the data centre. `LOW`, `MEDIUM` and `HIGH` all count as in stock. If the stock read itself fails, the check passes, because the create stays the authority and already fails safely.
- **Start history from pod sessions.** The developer panel's Render Offload tab shows, for the last 7 and 30 days:
  - pod start attempts and the share that started;
  - the median start-up time;
  - how often each GPU type was placed;
  - the number of starts that failed.

  All of this comes from the `render_pod_sessions` the app already records.
- **Stock sampling.** In pod mode, a background task reads the same live stock every 15 minutes and stores one row per configured GPU type. Rows are kept for 90 days. The panel shows the share of samples in which at least one configured GPU was in stock, the share per GPU type, the sample count and the time of the last sample. The developer can switch sampling off; it is on by default. A sample is a free read and never creates anything.

**Ladder step and agents:** none. This is render infrastructure and the developer panel only. **Render guard:** affected only by one more pre-approval refusal reason. Tiers, tickets, estimates and the typed approval are unchanged. **bpy allow-list:** not affected. The homeowner sees only the refusal reason, which names no host, cost or account detail.

**Depends on `render-pod-lifecycle`**: pod mode, the RunPod client and the pod sessions. Apply after that change is archived.

Deferred: volumes in several data centres (decide once the history shows real numbers).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `render-offload`: a stock check before approval in pod mode, and stock sampling with retention.
- `dev-panel`: the Render Offload tab shows start history and stock history, and a sampling switch.

## Impact

- Code:
  - `app/render/offload/runpod.py`: a v2 catalog read, `GET https://api.runpod.io/v2/catalog/gpus?include=AVAILABILITY&product=POD&cloud=SECURE`.
  - `app/render/offload/check.py`: stock as part of `check_runpod`.
  - New `app/render/offload/availability.py`: the sampler task and the history queries.
  - `app/main.py`: start and stop the sampler in the lifespan.
  - `app/api/admin_offload.py` and `frontend/src/routes/admin/Offload.tsx`: the history and the switch.
- Data: migration `0026_gpu_stock_samples` (after `0025_relabel_preview_tier` from `two-tier-renders`; renumber if the order of landing changes) (taken_at, data_center, gpu_type, availability); operator setting `offload:stock_sampling` (on by default).
- Dependencies: none (`httpx` already).
- Cost: none on Runpod. A stock read is a free API call, about 96 a day.
