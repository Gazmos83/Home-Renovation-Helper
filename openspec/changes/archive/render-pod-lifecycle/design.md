## Context

See proposal.md for the motivation. What exists today (`render-offload`):

- **Config and transport.** `OffloadConfig` (`transport.py`) is built from fixed `RENDER_OFFLOAD_*` settings. Every `ssh`/`scp` call carries `BatchMode`, `StrictHostKeyChecking=yes`, the owner's known-hosts file and the key, and runs through the injectable `Launch` seam.
- **Runtime.** `OffloadRuntime` (`runtime.py`) holds the config, the server's one-job lock and `OffloadChecker`. The checker runs `blender --version` over SSH within 10 s and caches a success for 60 s.
- **Pre-approval check.** It is called from `app/api/renders.py`, `plugins/render_turntable/tool.py`, `plugins/photoreal_detail/tool.py` (through `confirm_server_sync`) and `benchmark.py` (through `ensure_server`).
- **Job.** `runner.py` takes `offload.semaphore`, then `run_remote(...)` uploads, runs, pulls back and cleans up. `on_start` marks the start of render time used for calibration.
- **Records and settings.** Operator settings live in `benchmark_store` (`offload:final_target`, `offload:benchmark`, `offload:hourly_rate_eur`). Migration `0009_remote_render_jobs` holds the job list. The latest migration is `0023`.
- **HTTP.** `httpx` is already a dependency (`app/agent/models/prices.py` uses it with `follow_redirects=False`).

RunPod REST API (checked 2026-10-15, `https://rest.runpod.io/v1`, `Authorization: Bearer <key>`):
- `POST /pods` (body fields include `name`, `gpuTypeIds`, `gpuCount`, `cloudType`, `networkVolumeId`, `volumeMountPath`, `containerDiskInGb`, `imageName`, `ports`, `dockerStartCmd`, `dataCenterIds`) returns the pod with `id`.
- `GET /pods/{id}` returns `desiredStatus` (`RUNNING`/`EXITED`/`TERMINATED`), `publicIp`, `portMappings` (e.g. `{"22": 10341}`) and `costPerHr`.
- `DELETE /pods/{id}` returns 204.

## Goals / Non-Goals

**Goals:**
- Paid GPU time is only the start-up, the jobs and the idle time, and never starts before the typed "yes".
- The SSH security of `render-offload` is unchanged in pod mode: key only, host key pinned, commands built only from code.

**Non-Goals:**
- Other providers, or a provider-neutral plugin interface. RunPod only, by the owner's choice.
- Creating or filling the network volume from the app. That is a documented one-off owner step.
- Choosing a data centre automatically, or bidding on interruptible pods. (A GPU fallback list was added after the first live run, decision 11.)
- A spend limit in the app. The RunPod account's own limits stay the owner's backstop.

## Decisions

1. **Create and delete per session, not start and stop one pod.** A stopped pod is tied to its machine, and RunPod documents that it can restart with zero GPUs. A new pod from a network volume can land on any machine in the volume's data centre. The volume stores about 2 GB (Blender 1.2 GB, keys, kernel cache) at about $0.07/GB/month. *Alternatives:* start and stop one pod (the owner rejected it, 2026-10-15); RunPod Serverless (rejected: no SSH, needs a custom worker image, and replaces the tested remote job).

2. **REST client `runpod.py`.** It is a small class over `httpx.AsyncClient`:
   - a fixed base URL constant, `follow_redirects=False` and a 15 s timeout;
   - the key read from `SecretStr` only when the header is built, never put into an exception, a log or a record;
   - methods `create_pod`, `get_pod`, `delete_pod`, `list_pods` and `get_network_volume`;
   - errors mapped to safe reasons: 401 → "RunPod rejected the API key", 404 volume → "the network volume was not found", a GPU-capacity refusal → "no <type> is free on RunPod right now". Any other status → "RunPod answered <status>". Response bodies are not logged.

   Tests inject `httpx.MockTransport`. *Alternative:* the `runpod` Python SDK. Rejected because it adds a dependency for five calls.

3. **Pod body built only from constants and settings.**
   - `name="hra-render"` (the app-owned name used by cleanup), `gpuTypeIds=[the configured types, in order]`, `gpuTypePriority="custom"`, `gpuCount=1`, `cloudType="SECURE"`.
   - `networkVolumeId=setting`, `volumeMountPath="/workspace"`, `containerDiskInGb=10`, `imageName=setting`, `ports=["22/tcp"]`.
   - `dockerStartCmd` is a fixed constant. It first installs any `.deb` packages kept in `/workspace/hra/debs` (found while applying: the container disk is fresh on every pod, so system libraries Blender needs, and `sshd` if the image lacks it, would otherwise be missing). It then copies `/workspace/hra/ssh/ssh_host_ed25519_key*` into `/etc/ssh/`, copies `/workspace/hra/ssh/authorized_keys` to `/root/.ssh/`, and execs `sshd -D` with password login disabled.
   - `dataCenterIds=[volume.dataCenterId]`, read with `get_network_volume` before each create. Checked 2026-10-15: RunPod says "Network volumes are only available for Pods in the Secure Cloud", and the GPU choice depends on the volume's location. The pod docs do not say whether the data centre is implied, so it is passed explicitly.
   - The image must be pinned to a tag, and each GPU type is validated as a plain identifier.

4. **Host key alias.** The known-hosts file holds one entry for the alias `hra-render-pod`. In pod mode, `OffloadConfig` is completed per pod with `host=publicIp` and `port=portMappings["22"]`, and the SSH options add `-o HostKeyAlias=hra-render-pod`. Strict checking then verifies the volume's host key whatever the address. Fixed-host mode is unchanged. A pod whose key does not match fails like a changed host key.

5. **`PodManager` on the runtime.**
   - `OffloadRuntime` gains `pod: PodManager | None` (only in pod mode). It tracks `state` (`none`, `starting`, `running`, `delete_failed`), `pod_id`, the connection, `idle_deadline` and the current session id.
   - `ensure_pod()` runs inside `offload.semaphore` in the runner and the benchmark, before `on_start`, so start-up never counts as render time. It creates the pod, polls `get_pod` every 5 s until there is an address and port, then retries the SSH version check every 10 s until it passes or 10 minutes have passed.
   - `job_finished()` sets the idle deadline. A single `asyncio` task on the app loop sleeps until the deadline and deletes the pod only when `offload.semaphore` is free (`locked()` is false), re-reading the deadline first.
   - The idle minutes are read from operator settings at each job end, so a change applies to the next idle time without a restart.

6. **Pre-approval check in pod mode.** `OffloadChecker.check` branches:
   - pod running: the existing SSH version check against the pod's connection;
   - no pod: `get_network_volume` within the same 10 s limit.

   A success is cached for 60 s, as now. The callers (`confirm_server_sync`, `ensure_server`) are unchanged.

7. **Start-up in the estimate.** `offload:boot_seconds` is written after every successful start. `remote_benchmark_for(engine, target, offload)`, already called by the route and both tools, returns the stored remote benchmark with the start-up added to its overhead when the mode is pod and no pod is running. The guard and `estimate.remote_estimate_seconds` are unchanged, and the stored benchmark is never rewritten. Calibration is unchanged too: it reads the stored benchmark, and start-up happens before `on_start`.

8. **Sessions table.** Migration `0024_render_pod_sessions` has the columns `id`, `pod_id`, `gpu_type`, `cost_per_hr`, `created_at`, `ready_at`, `deleted_at`, `jobs`, `outcome` (`deleted_idle`, `deleted_manual`, `deleted_shutdown`, `orphaned`, `start_failed`, `delete_failed`) and `error`. Cost is computed on read as lifetime × `cost_per_hr` and is shown only on the developer route.

9. **Startup and shutdown cleanup in the lifespan.** At startup, `list_pods` runs, and every pod named `hra-render` is deleted and recorded as `orphaned`. A failure is logged and shown as `delete_failed`, then retried every minute. At shutdown, `delete_pod` runs with a 30 s cap.

10. **Owner setup, not app code.** `docs/runpod-setup.md` and `scripts/runpod/setup_volume.sh` hold the one-off setup, run by the owner in a RunPod web terminal on a temporary pod with the volume attached. The script downloads Blender 5.2.1 for Linux, checks its SHA-256 against the value published on blender.org, unpacks it into `/workspace`, saves the system packages the image lacks for Blender and `sshd` into `/workspace/hra/debs` (downloaded with `apt-get --download-only` on a setup pod running the same image), checks that Blender starts headless with them, generates the ed25519 host key into `/workspace/hra/ssh/`, and installs the owner's public key. It then prints the `hra-render-pod ssh-ed25519 …` line for the known-hosts file. The app never runs this script.

11. **GPU priority list** (added 2026-10-15 after the first live run). In one afternoon the RTX 4090 and then the RTX A4500 sold out in EU-RO-1, and the benchmark was refused with `"create pod: There are no instances currently available"`. `RENDER_OFFLOAD_RUNPOD_GPU_TYPE` now takes up to five comma-separated types in priority order. The create sends them all with `gpuTypePriority="custom"`, which RunPod documents as "always try to rent GPU types in the order specified in gpuTypeIds". The session records the type the pod got (`gpu.id`, else `machine.gpuTypeId`). The estimate still comes from the one remote benchmark, so a final on a faster or slower type than the benchmark's is estimated off; the first final recalibrates. *Alternative:* one type per create, with the app retrying the next. Rejected because RunPod already does the ordering in one call.

12. **Give up early on a pod RunPod never starts** (added 2026-10-15 after the second live run). RunPod placed the pod on machine `o5d2qxwjenu4` but never started its container: in 10 minutes it got no uptime, no public IP, no port mapping and no log line, and the full limit was paid ($0.15). `_wait_until_ready` now fails after 3 minutes (`ADDRESS_LIMIT_SECONDS`) if the pod has no address and SSH port yet. A pod that has an address keeps the 10-minute limit for SSH and Blender, because a slow first boot after the address is normal. The setup pod on the same image booted in about 3 seconds, so 3 minutes leaves wide room for an image pull on a cold machine.

    The same run showed no message on the panel. The benchmark request ran for over 10 minutes through the Vite dev proxy, whose default timeouts the config already turns off for `/chat`. `/admin/offload` now gets the same proxy settings, and an error answer without a reason shows its HTTP status instead of nothing.

## Risks / Trade-offs

- **No GPU free in the volume's data centre** → The job fails with a stated reason and nothing runs locally. The setup guide says to pick a data centre with good stock of the chosen GPU. Moving the volume is a manual step.
- **Secure Cloud only** → Network volumes are tied to Secure Cloud data centres (confirmed 2026-10-15), so the hourly price is the secure one (about $0.59–0.89 for an RTX 4090), not community's $0.34. This was accepted as the price of reliable starts.
- **App crash leaves a pod running** → It is billed until the app's next start deletes it. The developer panel and the RunPod console show it, and the owner's RunPod spend limit is the backstop.
- **Each start costs time** → 2–5 minutes of start-up is shown in the estimate and is paid. A 10-minute idle time lets several finals in a row share one pod.
- **RunPod API changes** → All calls go through one module with mocked tests. A failing call refuses or fails the render with a reason; it never falls back.
- **API key exposure** → The key is a `SecretStr`, used only when building the header. Tests assert that it does not appear in logs, errors, responses or records.

## Migration Plan

1. Deploy with no `RENDER_OFFLOAD_RUNPOD_*` values: nothing changes.
2. Owner runs the setup (decision 10), sets the values, removes `RENDER_OFFLOAD_HOST` if set, and restarts.
3. Run the connection test, then the remote benchmark (this creates the first pod), and switch finals to `remote`.

Rollback: unset the RunPod values, or set the target to `local`. Migration `0024` is additive.
