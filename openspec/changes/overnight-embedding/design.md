## Context

See `proposal.md` for why. Today:
- `ingest_version` (`backend/app/engineering/ingest.py`) runs in the caller's process, inside one `begin_nested` transaction. It embeds in batches of 4, with rights rechecked per batch, and commits nothing until publication.
- Vector reuse already exists, but only from *published* chunks of the same source, by content hash.
- The CLI (`ingest-file`) and the route `POST /admin/knowledge/{id}/ingest` both block until the run ends.
- The dev backend runs `uvicorn --reload`, so an in-process background task would die whenever a source file changes.
- Renders take `app.state.blender_semaphore`, an in-process `asyncio.Semaphore(1)`.
- `/usr/bin/systemd-inhibit` is present.

## Goals / Non-Goals

**Goals:** start and forget, survive the browser, terminal and backend reloads, resume after a restart, keep the laptop from sleeping while working, and show honest progress.

**Non-Goals:**
- Scheduling a start time. The owner chose start-now, so a start time is not built.
- A queue of several jobs.
- A Stop button. Stopping is done by ending the process; the run then shows as interrupted and can resume.
- Overriding the lid switch.
- GPU or remote embedding.
- Changing extraction or retrieval.

## Decisions

1. **The job is a detached worker process.**
   - The route creates a `knowledge_ingestion_runs` row in state `queued`. It then launches `[systemd-inhibit --what=sleep:idle --mode=block --who=HomeRenovationAgents --why="Embedding <title>" ] <python> -m app.engineering run-job <run_id>`, with `start_new_session=True`, a fixed argv, no shell, and output discarded. It returns the run at once.
   - A new session survives the reloader's restarts, a closed terminal and a closed browser.
   - Alternatives rejected: FastAPI `BackgroundTasks`, which dies on `--reload` and on a backend restart; and a systemd user service, which is more setup and has no per-run argv.
   - The launcher is injected, as `subprocess_launch` is for Blender, so tests never spawn processes.
2. **CLI parity.** `ingest-file VERSION PATH --background` stages the file in the foreground, then launches the same worker and prints `{"run": id}`. Without the flag, the CLI behaves as today but gains resume and progress.
3. **One job at a time.**
   - The worker takes a Postgres advisory lock (`pg_try_advisory_lock` on a fixed key) for its lifetime. If the lock is held, the run fails with "another ingestion job is running".
   - The route refuses earlier, with a friendly reason, when a `queued` or `running` run has a fresh heartbeat, or when `app.state.blender_semaphore.locked()`.
4. **Staged vectors.**
   - New table `engineering_staged_vectors`: `version_id` (FK, cascade), `content_hash`, `embedding vector(1024)`, `created_at`, primary key `(version_id, content_hash)`.
   - The worker splits ingestion into three steps:
     - **Prepare:** extract, rights-filter, and compute hashes and the total.
     - **Embed:** for each batch, recheck rights, skip hashes already in published chunks of the source or in staged rows, embed the rest, and insert staged rows in their own committed transaction.
     - **Publish:** the existing nested transaction recomputes nothing, takes vectors from staged or published rows, rechecks rights, replaces the chunks, then deletes the version's staged rows.
   - Retrieval reads only `engineering_chunks`, so staged rows are never searchable.
   - The synchronous path for reviewed blocks stays as it is. It is small and does not need a job.
5. **Rights withdrawal deletes staged rows.** `decide_rights` deletes the version's staged rows when the new current rights lack embedding or retention. A worker whose per-batch recheck fails does the same before ending in `failed`, with the right named.
6. **Progress and liveness.**
   - Migration columns on `knowledge_ingestion_runs`: `total`, `embedded`, `started_at`, `finished_at`, `heartbeat_at`, `worker_pid`, `kept_awake`.
   - States: `queued`, `running`, `published`, `failed`, `interrupted`.
   - The worker updates `embedded` and `heartbeat_at` after every batch, and before and after model loading.
   - Reading the latest run marks a `queued` or `running` run `interrupted` when its heartbeat is older than 5 minutes or its PID no longer exists. One batch takes seconds and the model loads in under a minute.
   - Time left is computed from this run's newly embedded passages and elapsed embed time. Reused vectors are counted as done but not in the rate.
7. **API.**
   - `POST /admin/knowledge/{id}/ingest` without reviewed blocks starts a job and returns 202 with the run. With reviewed blocks, it behaves as today.
   - `GET /admin/knowledge/{id}/runs/latest` returns the state, counts, time left, kept-awake flag and reason.
   - Resume is the same POST. It works because staged rows exist.
8. **View.** Engineering Knowledge polls the latest run every 5 s while it is `queued` or `running`, using the `refetchInterval` pattern from `InspectorView.tsx`, and stops polling otherwise. It shows the state line, a progress bar, the time left, "laptop kept awake" or "laptop may sleep", and Resume for `interrupted` or `failed` runs with staged progress.
9. **Batch size by measurement.** Add the setting `embedding_batch_size`, default 4, used by both the ingestion loop and `embed`. Measurements on 2026-10-18 under load: batch 4 took 0.9–1.4 s per passage, 16 took 1.4 s, 32 took 2.9 s; length-sorted batch 4 took 0.9 s and batch 1 took 0.8 s. A benchmark task repeats this on a quiet machine. The default changes only if an option is at least 20 % faster, with peak memory at or under about 2.6 GB, the headroom documented in `app/embedding.py`. Length-sorted ordering inside the embed step is adopted on the same terms.

## Risks / Trade-offs

- [The lid is closed overnight and the laptop suspends] → The inhibitor deliberately excludes the lid switch, and the view says to leave the lid open. After waking, the run shows as interrupted and resumes.
- [A render started during a job runs slower than its estimate] → Starting a job is refused during a render, but not the reverse. The render guard is unchanged; the owner chooses when to render.
- [An orphaned worker after a crash keeps the advisory lock] → The lock is session-bound and released when the process dies. The PID check marks the run interrupted.
- [Staged rows are left behind by an abandoned version] → Version deletion cascades. Rows are small: 1024 floats per passage, about 10 MB for the handbook.
- [The worker runs with the developer's database credentials outside the request] → It reads settings the same way the CLI does today. No secret enters argv; only the run UUID does.

## Migration Plan

1. Apply the Alembic migration: new columns are nullable or defaulted, plus the new table.
2. Deploy the code. Existing runs read as finished, since their state is unchanged.
3. Rollback: downgrade the migration, which drops the staged table and columns. Published chunks are untouched.
