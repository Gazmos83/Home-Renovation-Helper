## 1. Data

- [ ] 1.1 Add the Alembic migration: progress columns on `knowledge_ingestion_runs` (`total`, `embedded`, `started_at`, `finished_at`, `heartbeat_at`, `worker_pid`, `kept_awake`) and table `engineering_staged_vectors` (primary key `version_id, content_hash`, version FK cascade); verify upgrade, downgrade and re-upgrade on a throwaway database with no model drift.

## 2. Resumable ingestion

- [ ] 2.1 Split `ingest_version` into prepare, embed and publish steps, saving each batch's new vectors to staged rows in their own committed transaction and updating `embedded`/`heartbeat_at`; verify with the embedding override that a run stopped after N batches, then run again, embeds only the remaining passages, and that old chunks stay searchable until publication.
- [ ] 2.2 Publish from staged or published vectors with the existing per-block rights recheck, then delete the version's staged rows; verify search never returns a staged-only passage, and that a changed passage text is embedded again rather than reusing the old vector.
- [ ] 2.3 Delete staged rows in `decide_rights` when current rights lose embedding or retention, and in the worker on a failed recheck; verify both paths and that the next start names the missing right.
- [ ] 2.4 Add setting `embedding_batch_size` (default 4) used by the ingestion loop and `embed`; verify the default is unchanged and a configured value reaches the embedder.

## 3. Background job

- [ ] 3.1 Add the `run-job RUN_ID` worker command: takes the advisory lock, records PID, `kept_awake`, start and finish times and the final state and reason; verify with the embedding override that a queued run reaches `published`, and that a second worker fails with "another ingestion job is running".
- [ ] 3.2 Add the injectable launcher that starts the worker detached (`start_new_session`, fixed argv, no shell), wrapped in `systemd-inhibit --what=sleep:idle --mode=block` when available; verify the exact argv with and without the inhibitor, using a fake launcher (no process spawned in tests).
- [ ] 3.3 Change `POST /admin/knowledge/{id}/ingest` to start a job (202 with the run) when no reviewed blocks are given, refusing while a fresh job runs or `blender_semaphore` is held; keep reviewed blocks synchronous. Verify all three refusals or outcomes and the unchanged reviewed-blocks path.
- [ ] 3.4 Add `GET /admin/knowledge/{id}/runs/latest` with counts, time left (from newly embedded passages only) and the interrupted rule (heartbeat older than 5 min or a dead PID); verify the time-left maths, both interrupted triggers, and that a finished run is reported unchanged.
- [ ] 3.5 Add `ingest-file … --background`, which stages in the foreground, launches the worker and prints `{"run": id}`, while the CLI without the flag gains resume and progress; verify both modes with the fake launcher.

## 4. View

- [ ] 4.1 Show the latest run on the Engineering Knowledge view: state, "Embedding N / total passages", time left, "laptop kept awake" or "laptop may sleep", polling every 5 s only while queued or running; verify with Vitest using fake timers that polling starts and stops and the texts appear.
- [ ] 4.2 Make "Run authorised ingestion" start the job and add Resume for interrupted or failed runs with staged progress; verify the refusal reason is shown when another job runs, and that no rights or review field changes.

## 5. Measurement and checks

- [ ] 5.1 Benchmark on a quiet machine (load average under 1) batch sizes 1, 4, 8 and 16, random and length-sorted, on 96 handbook passages; record the results here, and change the default or adopt sorting only if one is at least 20 % faster with peak memory at or under 2.6 GB.
- [ ] 5.2 Run backend tests on a throwaway database, `ruff check .`, `pnpm test`, `pnpm lint` and `pnpm build`; record the results here.
- [ ] 5.3 Browser and overnight check by the owner: start the handbook ingestion from the view, close the browser, confirm the next morning that it published with start and finish times, and that `systemd-inhibit --list` showed the job's inhibitor while it ran. Also interrupt one run (stop the worker) and confirm it shows as interrupted and resumes from its progress.

Measurements 2026-10-18 (under load, average about 7 on 8 cores; 2,391 passages from `engineering-pdf-passages`): batch 4 0.909 s and later 1.402 s per passage; batch 16 1.422 s; batch 32 2.890 s; length-sorted batch 4 0.909 s; batch 1 0.814 s; length-sorted batch 8 1.138 s. Peak RSS 2.3 GB at batch 4 and 3.4 GB at batch 32. Full run about 35–55 minutes.
