## Context

See proposal.md for the motivation. What exists today:

- **Ticket and launch.** `run_render(ticket, …)` builds argv from the ticket's tier (`--tier-frames/--tier-resolution/--tier-engine`), launches through `launch_guarded` under `app.state.blender_semaphore`, verifies the staging folder (`_verify_render`) and publishes it (`_publish_render`). `Launch` is an injectable `(argv, cwd, timeout) -> LaunchResult`, which is what tests fake.
- **Estimate and calibration.** `estimate.py` computes `frames × MP × multiplier × benchmark`. `calibration.py` replaces the Cycles multiplier after the first approved final. The benchmark ticket is minted by the guard (`BENCHMARK_TIER`).
- **Generators.** They import `app.blender.cli`, `_render` and `_scene` from `backend/app/blender/`, and `_render.py` fixes `scene.cycles.device = "CPU"`.
- **Other changes.** `photoreal-detail` adds `source` (model/detail) to the quote and the live socket that shares the local semaphore. `feedback-capture` adds `render_runs`. This change works with or without them; the render-guard delta assumes `photoreal-detail` has landed, because it names live-socket commands.

## Goals / Non-Goals

**Goals:**
- An approved final can take minutes on a rented GPU, with the same guard, estimate wording, verification and publish as a local one.
- The server is the owner's machine: started, stopped and paid for by hand. The app only uses it when it is configured and chosen.

**Non-Goals:**
- Provisioning, starting or stopping instances. Vendor APIs. Spend tracking beyond an informational euro estimate.
- Offloading drafts, previews, builds or the live detail pass.
- Several servers, or a queue persisted across restarts. An orphaned remote job is swept like a local one, and its folder is removed by the stale sweep (decision 5).

## Decisions

1. **System OpenSSH through the existing `Launch` seam.** `app/render/offload/transport.py` builds argv lists for `ssh` and `scp` and runs them with `subprocess_launch`, so tests use the existing fake launcher. Every call carries `-o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<file> -o IdentitiesOnly=yes -o ConnectTimeout=10 -i <key> -p <port>`. *Alternative:* `asyncssh` or `paramiko`. Rejected because they add a dependency and their own host-key handling, while the system client does pinning and key handling well, and `Launch` already fits.

2. **Remote commands built only from code.** The remote command is a single string for the remote shell. It is assembled only from:
   - constants (the remote root `~/hra-render`);
   - a job id (`uuid4().hex`);
   - the configured Blender path, validated at startup as an absolute path of `[A-Za-z0-9._/-]`;
   - the tier's integers and engine identifier;
   - the device enum;
   - fixed file names.

   Every component goes through `shlex.quote`. Package ids, model output and owner text never reach it. Tests assert this on argv.

3. **Bundle.** The generator bundle is the minimal set of files under `backend/app/blender/` that the render generators import: `cli.py`, `generators/{_render,_scene,render_still,render_turntable,build_room_scene}.py`, and `app/render/viewer.py` with its `viewer.html` template (the turntable generator imports it), plus anything else they import, determined by task 2.1 and asserted by a test that runs the bundle with Blender's Python alone. It is uploaded per job with `PYTHONPATH` set to the job folder. *Alternative:* a persistent install on the server. Rejected because it would drift from the laptop's version.

4. **Job sequence** (`app/render/offload/job.py`), run in place of `launch_guarded`'s local launch when the quote's target is `remote`:
   1. Consume the ticket (same `matches` check).
   2. Hold the server's own lock (`OffloadRuntime.semaphore`, held on `app.state.offload`).
   3. `ssh mkdir`.
   4. `scp` the blend file (`model.blend`, or `detail/detail.blend` for a detail source), the room document if any, and the bundle.
   5. `ssh` the generator with `--out <job>/out --cycles-device <dev>` and the tier arguments, under the tier timeout. A remote-side `timeout` wraps the command so the process dies with the connection.
   6. `scp -r` `out/` into the local staging folder.
   7. Run `_verify_render` and `_publish_render` unchanged.
   8. In `finally`, `ssh rm -rf <job>`. A cleanup failure is logged and does not fail a published render.

   Transfer seconds (upload + download) are measured separately.

5. **Stale sweep.** Each job starts with `find ~/hra-render -mindepth 1 -maxdepth 1 -mmin +1440 -exec rm -rf {} +`. This is a fixed string, bounded to the job root, and removes folders orphaned by a restart.

6. **Pre-approval check.** `quote()` stays pure. The render tool and route call `offload.check()` before `quote()` whenever the tier is `final` and the target is `remote`. It runs `ssh … <blender> --version` with a 10 s total cap and accepts the first line `Blender 5.2.1`. The result is cached for 60 s so a quote followed by an approval does not re-check twice. A failure raises `RenderRefused` with the owner-facing reason.

7. **Estimate.** `RenderQuote` gains `target: Literal["local","remote"] = "local"`. For a remote quote, `estimate.py` adds `remote_seconds(frames, mp, spmp, overhead)`, and the summary words it "on the render server, about N minutes". The remote benchmark is stored in operator settings (`offload:benchmark`: spmp, overhead, measured_at). It runs a one-frame, one-megapixel Cycles render through a guard-minted ticket with a new `REMOTE_BENCHMARK_TIER`, mirroring the local benchmark, using a fixed reference package. Calibration after the first approved remote final replaces spmp with `(actual − transfer) / (frames × mp)`.

8. **Records.**
   - `log_render_started/finished` gain `target`, and `transfer_seconds` for remote.
   - Table `remote_render_jobs` (id, package_id, version, render_key, estimate_seconds, actual_seconds, transfer_seconds, outcome, error, started_at) feeds the developer job list.
   - The euro figure is computed on read from `offload:hourly_rate_eur` and never stored or shown to the homeowner.

9. **Settings.** `RENDER_OFFLOAD_HOST`, `_PORT` (22), `_USER`, `_KEY_PATH`, `_KNOWN_HOSTS_PATH`, `_BLENDER`, `_CYCLES_DEVICE` (`OPTIX`). All are validated at startup; the startup summary shows "offload: off" or "offload: <user>@<host>:<port>". The key and known-hosts paths are checked for existence and readability only, and never read into memory or logs.

## Risks / Trade-offs

- [GPU Cycles output differs slightly from CPU (noise, denoiser)] → The finals are judged as finals. The tier fixes resolution and frames. The device is visible on the developer job list.
- [Large blend uploads on a slow link] → The overhead is measured by the benchmark and included in the estimate. Blend files of single pieces are small. Room renders upload only the room document plus the package blend.
- [The owner forgets the box is running] → Out of scope by decision. The Offload page shows the last job time and the euro estimate as a reminder.
- [A compromised server returns malicious files] → Only the expected PNG names are accepted by verification, and only after size and resolution checks. Nothing from the server is executed locally. After copy-back, the runner discards the remote `viewer.html` and writes it again locally with `render_viewer` for the tier's frame count, so no HTML from the server is ever published.
- [The SSH client is missing on the laptop] → The connection test and the pre-approval check report it as unreachable, naming `ssh`.

## Migration Plan

Migration `0009_remote_render_jobs`. The new settings default to off, so behaviour is unchanged until configured. Rollback: set the target to `local` or unset the settings, then drop the table.
