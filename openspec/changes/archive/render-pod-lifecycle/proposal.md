## Why

Today the render server is a machine the owner starts and stops by hand (`render-offload`), so it is billed for every minute it is left on, including the time spent remembering to switch it off. The owner asked (2026-10-15) for the app to start the rented GPU only for a `final` and shut it down again, to keep paid time as short as possible. The owner chose RunPod after a price comparison, with pods created on demand from a network volume and deleted after 10 idle minutes. This reverses the `render-offload` non-goal "no vendor APIs, no starting or stopping instances".

## What Changes

- **RunPod pod mode.** A second way to configure offload, alongside the existing fixed SSH host. It needs a RunPod API key, a network volume id, a GPU type and a pinned container image, plus the existing key file, known-hosts file, remote Blender path and device. When pod mode is configured, the app owns the server's lifetime. The fixed-host mode is unchanged.
- **Created on demand.** An approved remote `final`, or the remote benchmark, creates a pod with the network volume attached when none is running, waits for SSH, checks Blender 5.2.1, then runs the existing remote job. A running pod is reused.
- **Deleted when idle.** When no remote job has run for the idle time, the app deletes the pod. The default is 10 minutes, settable in the developer panel from 1 to 120. The network volume keeps Blender, the authorised key and the SSH host key between pods.
- **Never outlives the app.** At startup, the app deletes any pod it created that is still running, and it deletes its pod on shutdown. A failed delete is retried and is shown on the developer panel until it succeeds.
- **Check before approval, boot after.** Before a remote `final` is quoted with no pod running, the app checks without starting anything: the RunPod API answers with the key and the network volume exists. Paid time starts only after the typed "yes". A pod that cannot be created or does not answer over SSH in time fails the job with a stated reason. The pod is deleted, and the render never falls back to the laptop.
- **Estimate includes start-up.** When no pod is running, the remote estimate adds the measured start-up time (180 seconds until the first measurement). The homeowner sees time only, never a host or a cost.
- **Host key still pinned.** The pod's SSH host key lives on the network volume, and the known-hosts entry is keyed by a fixed alias, so strict host-key checking works even though each pod has a new address and port.
- **Developer panel.** The Render Offload tab shows the mode, the pod's state (none, starting, running with the time it will be deleted), a "Delete pod now" action, the idle-minutes setting, and pod sessions with their lifetime and cost from RunPod's reported hourly price. The API key is never shown.

**Ladder step and agents:** no ladder change, and no agent changes. It applies wherever a remote `final` already runs, at step 1 and for `photoreal-detail` finals. **Render guard:** affected only in the estimate (start-up time added). Tiers, tickets and the typed approval are unchanged. **bpy allow-list:** not affected. Only the fixed generators run on the pod.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `render-offload`: adds pod mode (configuration, create on demand, delete when idle, cleanup at startup and shutdown); the pre-approval check and the estimate change when pod mode has no running pod.
- `dev-panel`: the Render Offload tab shows pod state, the idle setting, "Delete pod now" and pod sessions.

## Impact

- Code:
  - New: `app/render/offload/runpod.py` (REST client for create, get, delete and list pods and get network volume; `httpx`, fixed host `rest.runpod.io`, no redirects, timeouts), `app/render/offload/pod.py` (pod lifecycle: create or reuse, wait for SSH, idle timer, startup and shutdown cleanup).
  - Changed:
    - `app/config.py`: `RENDER_OFFLOAD_RUNPOD_*` settings, with the API key as `SecretStr`.
    - `app/render/offload/transport.py`: host and port can come from the running pod; `HostKeyAlias`.
    - `app/render/offload/runtime.py` and `check.py`: the pod-mode pre-approval check.
    - `app/render/estimate.py`: start-up time.
    - `app/blender/runner.py` and `app/render/offload/benchmark.py`: ensure a pod before the job and mark activity after it.
    - `app/main.py`: lifespan startup and shutdown cleanup.
    - `app/api/admin_offload.py` and `frontend/src/routes/admin/Offload.tsx`.
- Data:
  - Operator settings `offload:idle_minutes` and `offload:boot_seconds`.
  - Migration `0024_render_pod_sessions` (pod id, created, deleted, hourly price, jobs, outcome).
- Dependencies: none added; `httpx` is already a dependency.
- Owner setup (README): create a 10 GB network volume (Runpod's minimum) in a data centre that offers the chosen GPU, and run the documented one-off setup pod to install Blender 5.2.1 and the SSH keys on it.
- Docs: CLAUDE.md §2 "Render server" row and §6 mention that a RunPod pod is created and deleted by the app.
