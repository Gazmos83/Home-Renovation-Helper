## Why

A `final` Cycles turntable is 36 frames at 1500 × 1500. On the XPS 13's CPU the guard estimates about 100 minutes at the default multiplier, and the laptop is unusable meanwhile. DESIGN_NOTES ("Deferred and undecided") notes that a few euros an hour of rented GPU turns that into minutes. The owner asked for this step (§11 step 10, "only if asked") and chose a generic SSH host they start and stop by hand: no vendor SDK or API key, and the app never rents or releases machines.

## What Changes

- **Render server over SSH.** It is configured only from settings (host, port, user, key file, pinned known-hosts file, remote Blender path, Cycles GPU device type) and is off unless all of them are set. It uses the system OpenSSH client with key-only, batch-mode, strict host-key checking. No password is ever used or stored.
- **Only `final` renders offload.** Draft and preview stay on the laptop's Eevee. The target for finals (`local` or `remote`) is a developer-panel setting with `local` as the default. There is **no automatic fallback**: when the target is remote and the server is unreachable or runs another Blender version, the final is refused with a stated reason before approval. The owner starts the box or switches the target.
- **Same guard, same publish.** The guard still issues the ticket, shows the estimate and needs the typed `yes`. The remote job uploads the blend file and the generator bundle to a per-job folder, runs the same headless command with the tier's values and the GPU device, pulls the output into the local staging folder, and uses the existing verification and atomic publish. The remote folder is removed afterwards.
- **Remote estimate.** A remote benchmark measures seconds per megapixel on the server's Cycles GPU plus a fixed transfer overhead. It runs only from the developer panel and only through the guard. The first remote final recalibrates it, like the local Cycles multiplier. The homeowner sees "on the render server, about N minutes". The euro estimate from a configured hourly rate shows only on the developer panel.
- **One process per machine.** At most one local and one remote Blender process at a time. A local draft can run while a remote final renders. **BREAKING (spec):** the render-guard requirement "One Blender process at a time" becomes "one per machine".
- **Generator flag.** `--cycles-device` sets `CPU` or a GPU type (`OPTIX`, `CUDA`, `HIP`). The default stays `CPU`, so local behaviour is unchanged.
- **Developer panel Offload page.** Configuration summary (host shown, key path and known-hosts contents never shown), connection test (reachability, remote Blender version, GPU device list), the remote benchmark, the target switch, and the last remote jobs with estimate, actual, transfer time and euro estimate.

**Ladder step and agent:** no ladder change. It applies to the `final` tier at step 1 and to step-3 detail finals (`photoreal-detail`) alike. Agents: none changed. The Builder's and Lighting's render tools are unchanged; only where the run happens differs. **Render guard:** affected. The quote names the target and uses the remote estimate. The one-process rule becomes per machine. Start and finish records carry the target. Approval, tiers and ticket rules are unchanged. **bpy allow-list:** not affected. No agent-written code goes to the server; only the fixed generators run there.

## Capabilities

### New Capabilities
- `render-offload`: the render server configuration, connection checks, the remote job (upload, run, pull back, clean up), remote estimate and benchmark, and the no-fallback rule.

### Modified Capabilities
- `render-guard`: one Blender process per machine; the estimate and the start/finish records name the target.
- `dev-panel`: the Offload settings, connection test, benchmark, target switch and job list.
- `studio-ui`: the developer route tree gains the Offload page.

## Impact

- Code:
  - New: `app/render/offload/` (settings check, SSH transport over the existing `Launch` abstraction, remote job, remote benchmark store), `app/api/admin_offload.py`, `frontend/src/routes/admin/Offload.tsx`.
  - Changed: `app/render/guard.py` (target in quote), `app/render/estimate.py` (remote formula), `app/render/records.py` (`target`), `app/blender/runner.py` (dispatch to the remote job, second semaphore), `app/blender/cli.py` and `generators/_render.py` (`--cycles-device`), `app/config.py` (`RENDER_OFFLOAD_*`), `app/main.py` (`app.state.offload`, the runtime that holds the server's own lock).
- Data:
  - Operator settings `offload:final_target`, `offload:benchmark` and `offload:hourly_rate_eur`.
  - Migration `0009_remote_render_jobs` for the developer's job list.
  - Nothing about the target or the host is written into the version folder, whose files the homeowner's routes serve.
- Dependencies: none added. Uses `ssh` and `scp` from the system.
- Tests: config gate (any missing value → off), argv of every SSH/SCP call (options present, no shell metacharacters from inputs), refusal before approval when unreachable or the version mismatches, remote job happy path with a fake transport (verification and publish reused), cleanup on failure and timeout, no fallback to local, local draft running beside a remote final, estimate and calibration maths, records with `target`, no host or euro figure in homeowner responses. A `--blender` test applies the render settings with `--cycles-device CPU` and with a GPU type and inspects `scene.cycles.device` without rendering. The existing `--blender` renders stay at tier `draft` and unchanged.
- Owner setup (documented in README): rent a GPU box, install Blender 5.2.1, add the public key, record the host key in the known-hosts file, and set the env values.
