## Context

The Design Studio (`src/routes/Studio.tsx`) has a `TABS` list; a tab with `dev: true` sits below a divider and is served from its own route tree through `fixedTab` (`<Studio dev fixedTab="agents" />` on `/admin/agents` and `/admin/agents/:tab`). `src/routes/admin/AgentSettings.tsx` holds `AGENT_VIEWS` and `AgentSettingsTab`, which picks the view body or redirects to the default view; `useSubMenu` lists the views. The pages to move are full pages today: `GuidelineNotes.tsx` (`<Page>`, `<h1>Guideline notes</h1>`, notes, `NoteForm`, `<HardwareDataSection />`), `admin/Guidelines.tsx` (`<h1>Guidelines</h1>`, "Upload a PDF", source table), `admin/Knowledge.tsx` (`<h1>Engineering knowledge</h1>`, still being finished by `furniture-engineering-rag-foundation` task 6.2) and `admin/Rules.tsx` (`<h1>Design rules</h1>`, `<h1>Open items for you</h1>`, a `<Page>Loading…</Page>` early return). `require_dev` is the dev-panel switch plus the owner session, so the developer always passes the owner gate the notes and data-sheet APIs use.

## Goals / Non-Goals

**Goals:** the three pages as views of one developer tab, built exactly like AI & Agent Settings; one Guidelines view; no lost behaviour for the developer; frontend-only diff.

**Non-Goals:** no API, gate, corpus or `search_guidelines` change; no restyle of the forms; no change to what Engineering Knowledge or Design Rules do.

## Decisions

- **Copy the AI & Agent Settings pattern.** A new `src/routes/admin/DesignKnowledge.tsx` exports `KNOWLEDGE_VIEWS` (`guidelines` "Guidelines", `engineering` "Engineering Knowledge", `rules` "Design Rules") and `DesignKnowledgeTab`, which redirects an unknown view to `/admin/design-knowledge/guidelines`. `Studio.tsx` gains a `TABS` entry `{ id: "design-knowledge", label: "Design Knowledge", icon: BookOpen, base: "/admin/design-knowledge", dev: true }` after `agents`, and a `useSubMenu` branch like the `agents` one. The divider logic already draws one divider before the first developer tab. Alternatives — a sub-menu inside AI & Agent Settings, or `/studio/...` addresses — were set aside: the owner chose a separate tab, and developer tabs keep the developer route tree.
- **Routes.** `App.tsx` serves `/admin/design-knowledge` and `/admin/design-knowledge/:tab` with `<Studio dev fixedTab="design-knowledge" />` behind the same `signedIn && dev` check as `/admin/agents`. `/guidelines`, `/admin/guidelines`, `/admin/knowledge` and `/admin/rules` become `<Navigate>` redirects to their view for the developer and to `/pieces` (or `/login`) otherwise, as `/admin/models` does. The homeowner `links` loses "Guidelines"; `adminLinks` is emptied and removed with its divider span.
- **Pages become view bodies.** Each loses `<Page>`, and its `<h1>` becomes an `<h2>` (Rules' "Open items for you" too) because the Studio already renders `<h1>Design Studio</h1>`. Rules' loading return becomes a plain `<p>Loading…</p>`. Default exports stay, so `KNOWLEDGE_VIEWS` imports them like `AGENT_VIEWS` imports the agent pages.
- **Guidelines view.** `GuidelineNotes.tsx` moves to `src/components/GuidelineNotesSection.tsx` next to `HardwareDataSection`, as a `<section aria-label="Guideline notes">` with an `<h2>`, without `<HardwareDataSection />`. `admin/Guidelines.tsx` renders, in order, a "Guideline PDFs" section (current upload form and source table), `GuidelineNotesSection`, `HardwareDataSection`. PDFs first because that is what the page showed until now (assumption; trivially reordered).
- **Ambiguous labels.** The upload form and the note form both label a field "Title". IDs already differ (`guideline-title` vs `title-new`), so the DOM is valid; tests scope queries with `within(form)`.
- **Tests move with the code.** `GuidelineNotes.test.tsx` becomes `components/GuidelineNotesSection.test.tsx`. A `DesignKnowledge.test.tsx` mirrors `AgentSettings.test.tsx`. `Knowledge.test.tsx` and `Rules.test.tsx` change only where they asserted an `<h1>`. `App.test.tsx`'s header test changes from "keeps Guidelines, Knowledge and Rules" to "has no developer entries" — a necessary test change, since the spec it checked changes.

## Risks / Trade-offs

- [The owner loses note and data-sheet management whenever the dev panel is off] → Owner's explicit choice (2026-10-15); stated in the proposal. Data and agent behaviour are untouched; switching the panel on restores the UI.
- [`studio-pricing-and-agent-settings-tabs` is not archived; this change modifies the requirement it adds] → Archive it first (task 1.1); validation of this change's MODIFIED delta depends on it.
- [`furniture-engineering-rag-foundation` task 6.2 is still editing `Knowledge.tsx`] → Make only the wrapper/heading edit there, and run that change's browser check on the Engineering Knowledge view.
- [Old bookmarks] → Redirects cover all four old addresses.

## Migration Plan

Frontend-only; ship and reload. Rollback is reverting the commit; no data moves.
