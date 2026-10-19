## Why

Ingesting a large engineering source ties up an open terminal or a blocking browser request for the whole run, with no progress shown. An interruption discards all work, because vectors are kept only in memory until the final atomic publish. On 2026-10-17 the Wood Handbook run silently stopped and left no record. The owner wants to start a run, leave the laptop, and find the result in the morning (decided 2026-10-18).

Measured on 2026-10-18 with the passages from `engineering-pdf-passages`: the new handbook (2,391 passages) takes about 35–55 minutes to embed on this laptop, depending on load. Larger embedding batches were slower, not faster (batch 4: 0.9–1.4 s per passage; 16: 1.4 s; 32: 2.9 s, with more memory each step).

## What Changes

- **Background ingestion job.** "Run authorised ingestion" on the Engineering Knowledge view, and `ingest-file --background` on the CLI, start ingestion as a detached worker process. They return at once with a run ID. The worker keeps running when the browser or terminal closes and when the dev backend reloads. Only one ingestion job runs at a time.
- **Resume after interruption.** Each finished batch of vectors is saved to a staging area keyed by the passage's content hash. A new run for the same version reuses them and embeds only the rest. Staged vectors are never searchable. Publication stays all-or-nothing, so the current blocks stay searchable until the last passage is embedded and rights are rechecked. Staged vectors are deleted after publication and when the version loses embedding or retention rights.
- **Keep the laptop awake.** The worker holds a systemd sleep and idle inhibitor for exactly the life of the job. Closing the lid still suspends: the lid switch is deliberately left alone.
- **Progress.** The run records passages embedded out of the total, a heartbeat, and start and finish times. The view polls while a job runs and shows, for example, "Embedding 812 / 2,391 passages · about 25 min left · laptop kept awake". A run whose heartbeat stops is shown as interrupted, with a Resume action.
- **Batch size measured, not assumed.** The embedding batch size becomes a setting, default 4 (today's value). A benchmark task on a quiet machine compares batch sizes and length-sorted ordering. The default changes only if one is at least 20 % faster without exceeding the memory headroom noted in `app/embedding.py`.
- **Not changed:** rights checks and their recheck before publication, the remote-use boundary, verification rules, extraction (`engineering-pdf-passages` owns it), the official-link fetch rules, and the render guard. Starting a job is refused while a headless render holds the render semaphore. A render started during a job is not blocked.

**Ladder step:** none. **Agents:** none changed. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engineering-knowledge`: adds a requirement that interrupted ingestion resumes from staged vectors without making them searchable or bypassing rights.
- `dev-panel`: adds a requirement for starting ingestion as a background job, one at a time, with progress, an interrupted state and resume.

## Impact

- **Backend:**
  - `app/engineering/ingest.py`: staged-vector lookup and save per batch, and progress updates.
  - A new worker entry point in `app/engineering/__main__.py` (`run-job`), and `ingest-file --background`.
  - `api/admin_knowledge.py`: the ingest route starts a job instead of blocking; a new route reads the latest run.
  - A rights-decision hook that deletes staged vectors on withdrawal.
  - A setting for the embedding batch size.
- **Database:** one Alembic migration. It adds progress columns to `knowledge_ingestion_runs` (total, embedded, heartbeat, start and finish times, worker PID) and a new table `engineering_staged_vectors`.
- **Frontend:** `routes/admin/Knowledge.tsx` (start, progress, resume) and its tests; `lib/api.ts`.
- **System:** uses `/usr/bin/systemd-inhibit`, which is present on this laptop. Without it, the job still runs, and the view says the laptop is not kept awake.
- **Order:** independent of `engineering-pdf-passages`. Its task 2.2 (re-ingest the handbook) can use this job once both are applied.
- **Cost:** about 2–3 developer days.
