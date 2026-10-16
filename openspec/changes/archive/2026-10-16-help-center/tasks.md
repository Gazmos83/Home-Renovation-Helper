## 1. Help source

- [x] 1.1 Write `backend/config/help.yaml` with the six topics in order (`blueprint`, `files`, `template`, `renders`, `conversations`, `workflow`). Carry the blueprint measurements and the file types over word for word from `Help.tsx`, and add the template steps, the default extraction prompt from design.md §8 and `download: import_template`. Verify by loading it in 1.2's test.
- [x] 1.2 Add `app/help.py`: strict Pydantic models (paragraph and list blocks, optional heading, prompt, download enum), loaded once at startup and raising `ConfigurationError` that names the file on a malformed source, an unknown field or a duplicate id. Verify with `tests/test_help.py`: the shipped source loads with the six ids in order; a duplicate id and an unknown field are refused by name; the template topic holds the six steps and the prompt's required phrases (JSON alone, millimetres, only guide fields, no survey).
- [x] 1.3 Add the owner-gated `GET /help` route and register it. Verify with a test: 200 with the topics for the owner, 401 without a session, and no model, token or cost in the body.

## 2. Chat

- [x] 2.1 Add `backend/plugins/help/` (manifest: role intake, not toggleable, enabled by default; `read_help` returning the topic list, or one topic's title, body and prompt wrapped with `wrap_passage`; an unknown id refused naming it and listing the valid ids). Verify with plugin tests for listing, reading `template`, refusing `pricing` and refusing a per-thread toggle-off.
- [x] 2.2 Add `asks_help` to the Foreman `Decision`, and in routing send a help question to Intake after the Researcher rule and before the no-room question, never when a plan, photo or design file is attached, without changing the confirmed room or bound piece. Update `foreman.md` with the rule. Verify with `test_foreman` cases: a help question in a new thread reaches Intake (not "Which room is this for?"); a help question in a bound thread keeps the piece; an attached design file with "how does this work?" still gets the room question; an existing wish, revision and render request route as before.
- [x] 2.3 Name `read_help` in `intake.md`'s header and add the help-turn rule (answer from `read_help` only, record nothing, raise no confirmation, say when not covered and point to Help). Verify with a scripted-model test that a help turn calls `read_help`, writes nothing to the house file and raises no interrupt.

## 3. Help page

- [x] 3.1 Add the help query to `lib/api.ts` and rewrite `routes/Help.tsx` to render the topics as collapsed `<details>` with the title as `<summary>`. Keep `ExampleRoom` under `blueprint`, add a `WorkflowDiagram` SVG under `workflow` whose title or description names every step, show the import-template download for `download: import_template`, and show the prompt in a `<pre>` with a Copy button ("Copied", or "Copy failed — select the text"). Show a stated error when the query fails. Verify with `Help.test.tsx`: all topics collapsed at first; expanding `blueprint` shows the measurements; the files topic lists PNG/JPEG, Markdown/plain text and `.json`; the download link points at the template route; Copy writes the exact prompt to the clipboard; the diagram's accessible name names every step; the error state is shown.
- [x] 3.2 Confirm the Pieces page still offers its template download (existing Pieces test passes unchanged).

## 4. Finish

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, and `pnpm lint`, `pnpm test`, `pnpm build` in `frontend/`. All pass.
- [x] 4.2 Browser pass on the running app: open Help, expand each topic, download the template, copy the prompt; in a new conversation ask "How do I use the design template?" and get Intake's answer instead of "Which room is this for?". No render runs, so no render tier is involved.
