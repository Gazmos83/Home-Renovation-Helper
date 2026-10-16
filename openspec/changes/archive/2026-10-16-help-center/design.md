## Context

- `frontend/src/routes/Help.tsx` hard-codes two sections and the `MEASUREMENTS` list; nothing on the backend can read it.
- The import template is already served by `GET /design-import/template` (owner-gated, `app/api/design_import.py`), and Pieces links to it through `downloads.importTemplate`. Importing an attached design file and revising it already work (design-import spec).
- The Foreman never answers and never calls a tool; its `Decision` already carries a boolean hint (`composes_room`) that code combines with application rules. With no confirmed room, any turn other than plan, photo or room name gets the fixed "Which room is this for?".
- Plugins bind a tool to a specialist when the manifest's role or `also_for` matches and the instruction header names the tool. YAML configuration lives in `backend/config/` and is loaded with strict Pydantic models that refuse unknown fields (`app/restyle/presets.py`).
- Retrieved text reaches a model inside the untrusted-content delimiters (`app/agent/prompts.py`).

## Goals / Non-Goals

**Goals:** one help source for the page and the chat; help questions answered in any conversation; a copyable extraction prompt and a template download on Help.

**Non-Goals:** editing help from `/admin`; search or embeddings over help; a new agent or model slot; any change to the import template, the import flow or the Pieces page.

## Decisions

1. **`backend/config/help.yaml` with a strict loader (`app/help.py`).** Shape: `topics: [{id, title, body: [block], prompt?: str, download?: "import_template"}]`. A block is either `{text: str}` (a paragraph) or `{items: [str]}` (a bullet list), and each block may carry an optional `heading`. This is enough for the existing text, and the frontend renders it without parsing Markdown. Loaded once at startup, like the looks; a malformed file raises `ConfigurationError` naming the file. *Alternative:* Markdown files per topic. Rejected: the page would need a Markdown renderer, and a topic's prompt and download would need conventions.
2. **`GET /help` (owner-gated) returns the topics as JSON.** The frontend fetches it with TanStack Query. `download` is an enum key, which the frontend maps to `downloads.importTemplate`, so a URL is never stored in the YAML.
3. **Diagrams stay in the frontend.** `ExampleRoom` and a new `WorkflowDiagram` are SVG components keyed by topic id (`blueprint`, `workflow`). The workflow topic's `body` lists the same steps in text, and that list is both the SVG's `<title>`/description and what the chat reads, so a screen reader and the bot see the same steps.
4. **Collapsible topics use native `<details>`/`<summary>`**, as `admin/Knowledge.tsx` already does. They are keyboard and screen-reader accessible with no new component. All topics start closed.
5. **Copy button** uses `navigator.clipboard.writeText(topic.prompt)`. The button's label changes to "Copied" for two seconds; on failure it says "Copy failed — select the text". The prompt is shown in a `<pre>` so it can also be selected by hand.
6. **Routing: `Decision.asks_help: bool`**, described to the Foreman as "the owner asks how to use the app, not for design, build, render, review or price work". In code, it is checked right after the Researcher rule and before the no-room fixed question, and only when the turn carries no plan, photo or design file. It sends the turn to Intake without touching `room_confirmed` or the bound piece. A pending confirmation still resumes first, as it does today. *Alternative:* give `read_help` to every specialist. Rejected: every specialist's prompt would grow, and with no room the turn never reaches a specialist anyway.
7. **`backend/plugins/help/`**: manifest `role: intake`, `toggleable: false`, `enabled_by_default: true`, tool `read_help(topic: Literal[...ids] | None)`. The ids are built from the loaded file, and an unknown id is refused listing the valid ids. The output is wrapped with `wrap_passage` (source `help`), so the help text is treated as data. `intake.md` gets the tool in its header and a short rule: on a help turn, call `read_help`, answer only from it, record nothing, and say when it is not covered.
8. **The default extraction prompt (in `help.yaml`):**

   > You are a furniture designer. The attached photo shows a piece of furniture I like, and the attached file `import-template.json` is a design template. Fill in the template's `build` so that it describes the piece in the photo: its overall size, its modules, shelves, dividers, fronts, materials and hardware. Follow the template's `guide` and use only the fields it names; do not add any other field. Give every size in whole millimetres; where the photo shows no measurement, estimate it from common furniture sizes. Keep `kind`, `schema_version`, `units` and `guide` exactly as they are, and do not add a room survey. Return the whole document as JSON alone, with no other text before or after it.

## Risks / Trade-offs

- [The Foreman flags a design request as help] → The flag never applies when a file is attached. Tests cover a wish, a revision and a render request staying where they go today; Intake records nothing on a help turn, so a misroute costs one reply, not data.
- [Help text and the app drift apart over time] → The help source is the only copy. `Help.test.tsx` and a backend test assert the six topic ids, the measurement list and the prompt's required phrases.
- [Another chat returns an invalid design] → The existing import validation refuses it by field name. The template topic says so.

## Migration Plan

No data migration. Ship the YAML, the loader, the route, the plugin and the page together. Rollback is a revert; the Pieces download is unaffected.
