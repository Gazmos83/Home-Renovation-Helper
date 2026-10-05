# Design Notes — why the app is shaped this way

Companion to `../CLAUDE.md`. That file says what to build; this one says why, so later changes can be judged against the original reasoning. Decisions recorded 2026-10-05.

## Context

- Personal project: the owner is renovating their own home and wants custom-made furniture. Not multi-tenant, not commercial.
- Hardware: Dell XPS 13, Linux, CPU only. Blender renders are the bottleneck, not LLM calls. Headless renders also run on this CPU; "no laptop processing" was never true, only "cheap per iteration".
- Predecessor: `Interior_Design_App`, a three-surface business product. It already holds a validated spec contract, headless generators with turntables, a cut-list deriver, a priced supplier list, a revision tool, Langfuse, a guard, plugins and feedback learning. This repo ports the parts that serve one homeowner and drops the rest.
- Course requirements still apply: ≥5 toggleable function tools, plugin system, multi-model support, memory, auth, a security guard, agentic RAG, external data source, learning from feedback, separate dev/user UX.

## Two budgets, not one

Token budget (OpenRouter) and render budget (laptop CPU) are independent. A premium model writing a lighting node graph is cheap and fast; Blender executing a 36-frame Cycles render is neither. The render guard exists because nothing else tracks the second budget. Langfuse, the admin token restrictions and OpenRouter's spend cap cover the first.

## Why a Foreman + specialists

- The homeowner talks to one thing and never sees model names.
- Each specialist runs on the model suited to it (course requirement: multi-model). Routing is a config file, so a swap is a one-line change.
- The criteria's five trades map onto the roles the owner finds easier to picture: Intake & brief stays; the Modeller splits into Designer (spec) and Builder (Blender); Lighting & materials, Reviewer and Researcher stay. Splitting the Modeller matters because the Designer only ever emits JSON while the Builder is the only runtime agent that can touch Blender.
- The Reviewer runs on a different model family from the Builder so it does not share the Builder's blind spots.

## Why the Designer outputs spec JSON, not raw bpy

The ported generator already turns JSON into geometry. Having the agent emit JSON means it can be schema-validated before anything touches Blender, reviewed by the owner in plain numbers, and read by the cut-list and cost tools without parsing Blender state. Raw `bpy` is reserved for step 3, where the carpentry detail needs operations the spec cannot express.

## Why a three-step ladder

The owner's working loop is: describe a change to the bot, confirm, see a new turntable in about half a minute. That is step 1 and it must stay the default. When the spec cannot express a change, the right fix is to grow the spec and generator (step 2), because every later package then benefits and the cut list stays truthful. Only one-off work that is not worth encoding goes to a live Blender (step 3), and it never writes a dimension back, so the spec remains the single source of truth. The ladder is enforced by the validator refusing unknown fields, not by prompting.

## Why both headless and live Blender

Headless is reproducible, cheap, needs no window and keeps the agent away from arbitrary code. The live socket is where photoreal detail, look-dev and camera matching happen, because those need the full `bpy` surface. Both go through the render guard, and the socket tool refuses to run while a headless job holds the semaphore so two Blenders never fight for the CPU. The socket is driven directly from the backend, not through Claude Desktop: Desktop has no API the backend can call, would lock Blender work to one vendor, make the guard prompt-only, lose traces and fail the "tools inside your app" requirement. Claude Desktop remains the owner's own workshop for prototyping step-3 scripts on a consumer subscription, which is the one place that licence may be used.

## Why the render guard is a graph node

Prompt instructions get ignored under pressure. A node with a required `tier` argument cannot be bypassed by a model deciding to be helpful. `interrupt()` on the final tier gives a real pause the UI renders as an approval dialog.

## Why per-render approval and no daily cap

Owner's choice. One sitting may legitimately involve many drafts; a daily cap would get in the way. The estimate shown before each render is the control.

## Why Eevee by default, screenshots for progress

On a CPU-only laptop Eevee is tens of times faster than Cycles and adequate for shape, proportion and layout. Cycles earns its cost only for the few final images. Viewport screenshots are near-instant; even a draft render is minutes, so the Builder looks at screenshots after every modelling step and renders only when a turntable is wanted.

## Why the scrollable turntable stays

The frame-scrub viewer is the owner's inspection tool: a stack of frames taken around the model, stitched into a page you drag. It is produced by the headless job from the spec, so it needs no live Blender and feeds the revise loop directly. The viewer page from the scroll-viewer skill is reused as the template written beside the frames.

## Why pricing stays, and where its boundary is

The owner's goal is to build the furniture, and a board list with a realistic materials total is worth more than a prettier render. Pricing was nearly dropped because of gaps in the old output: live lookup reached only products already in the corpus, manual snapshots were never exercised in a browser, and manual price entry was not visibly available. The rework closes those gaps with three lawful inputs to one table: a toom URL pasted directly, a hand-made entry, and a snapshot. The legal boundary does not move: the retailers that refused `robots.txt` stay excluded, and "web access" for the Researcher widens the set of permitted sources (building rules, spec sheets, asset libraries), not the set of retailers to scrape.

## Why one cheap model per agent and no backup

Validated output makes model choice less critical: the Designer's JSON is schema-checked, the Builder's scripts are allow-listed, and the Reviewer only lists discrepancies. So each slot runs on the cheapest model with a strong aggregate score that the owner's OpenRouter guardrail actually serves. Backups were dropped (2026-10-05) because the premium candidates are blocked by that guardrail, and an automatic fallback would hide cost and make traces harder to read. If a slot falls short, the owner changes its model by hand from the dev panel to another probed registry entry.

## Why token restrictions live in the admin panel

Per-model output caps, per-turn context budgets and a daily ceiling are the token-side twin of the render guard. They are enforced by the budget node before the call, surfaced to the owner as a stated refusal, and never visible to or alterable by the model.

## Memory shape

- Short-term: LangGraph checkpointer so a project survives closing the laptop.
- Long-term: the house file — every room's polygon, heights and openings, style preferences, pieces designed with their versions, render feedback, and generator-extension requests. Intake and Designer read it first, so each new piece starts with the room known.

## Feedback loop

Thumbs up/down plus optional comment on every turntable, stored with the prompt, model and tier used. Two uses: personalisation via the house file, and Langfuse tags so the owner can see which model does best at which task and adjust routing.

## Security guard choices

- Prompt-injection delimiters: web, retailer pages and uploads are the untrusted inputs.
- `bpy` allow-list: a live script is arbitrary Python on the owner's machine; the allow-list keeps agent mistakes inside Blender and the render folder.
- Single-user password auth with a separately gated dev route meets the requirement without a user system. Scope still comes from the cookie and path, never a model argument, as in the predecessor.

## Deferred and undecided

- Cloud GPU offload for finals: a few dollars an hour turns a two-hour local render into minutes. Not built until local finals are too painful.
- Apartment shells from photos are **in scope** (decided 2026-10-05): cheap to model headless, cheap to read with a cloud vision model; only Cycles finals are expensive, and those sit behind the guard like any other final.
