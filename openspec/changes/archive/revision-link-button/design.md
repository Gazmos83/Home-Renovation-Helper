## Context

`notices.post_build` and `follow_build` post a `build` notice through `house_file.add_notice` once a build ends; `Notice.tsx` renders it centered (`mx-auto … items-center text-center`) with "Inspect version N" for a succeeded build. `revise.record_next` (in `plugins/revise_package/tool.py`) creates the version and starts the build with `notices.follow_build`.

## Decisions

- **New notice kind `revision`, posted from `record_next`** right after `service.create_version` and `house_file.record_version`, via a `notices.post_revision` modelled on `post_build` (never raises, no-op without a thread). `rebuild_piece` goes through the same function, so it is covered.
- **Why not reuse the build notice:** it posts only when the build ends and only links on success. The link must exist at once.
- **Frontend:** `Notice.tsx` handles `kind === "revision"` with label "Open version N" and the existing `onReview` handler; styling stays the existing centered section.
- **Order:** the notice is placed after the messages the thread held when posted (`_message_count`), as other notices are.
- **API:** the `kind` and outcome fields are already carried; `outcome` is `succeeded` for a revision notice (the version exists).

## Risks

- The inspector must cope with a version whose build is still running (no render yet). To check at implementation; if it does not, show the existing building state rather than adding a new one.
- Two buttons per revision (Open version N, later Inspect version N). Accepted: the second is the "built" signal. TODO(user): say if the build notice should lose its button.
