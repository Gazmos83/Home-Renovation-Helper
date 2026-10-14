## Context

`App.tsx` lists eleven developer entries (`adminLinks`), each a route gated by `signedIn && dev`. The pricing pages were just combined the same way (`combine-pricing-pages`): `routes/Pricing.tsx` holds a link-based tab list and mounts only the chosen body. Each of the eight admin pages renders `Page`, an `h1`, and returns `<Page>Loading…</Page>` (and Workflow an error `Page`) while its query loads. `Models.tsx` has a second `h1`, "Generation and budgets".

## Goals / Non-Goals

**Goals:** one AI & Agent Settings page with eight tabs under the owner's names; each tab linkable; old addresses keep working; no change to any form, table, graph, refusal or query key.

**Non-Goals:** no new API or backend change; no restyling; Guidelines, Knowledge and Rules stay separate pages; no shared tab component.

## Decisions

- **Names and order.** Page title and nav label "AI & Agent Settings"; tabs in the owner's order: Agent Memory, Agent Workflow, Agent Calls, Render Offload, Agent Score, Token Usage, Plugins, Models and Routing. The first tab, Agent Memory, is the default. The owner kept the listed order (2026-10-14) and asked that the page sit in the top navigation bar.
- **Address.** `/admin/agents/:tab` with `tab` one of `memory`, `workflow`, `calls`, `offload`, `score`, `usage`, `plugins`, `models`; `/admin/agents` and an unknown tab go to `/admin/agents/memory`. `/admin/agents` has no backend route, and `/admin` is already a page path in the Vite proxy, so a reload gets the app. Path segment, not `?tab=`, as in Pricing.
- **Old addresses redirect.** The eight old routes become `<Navigate replace>` to their tab, still behind the dev gate (a non-developer is sent to `/pieces` as today).
- **Tabs on a left rail like Pricing Overview's.** The owner asked (2026-10-14) for the tabs at the page's left with the same font, colour scheme, icon style and "Hide labels" switch as the Pricing Overview and conversation pages. `AgentSettings.tsx` uses the rail pieces `combine-pricing-pages` extracted from `components/chat/Rail.tsx` — `railClass`, `railItemClass`, `RailLabelsToggle`, `useRailLabels` — with the same markup as `Pricing.tsx`: a vertical `role="tablist"` labelled "AI & Agent Settings" of eight `role="tab"` icon links (`aria-label`, `aria-selected`, `aria-controls`), the chosen one on `bg-accent`, the switch at the rail's foot, and one `role="tabpanel"` beside the rail. Lucide icons: Brain (Agent Memory), Workflow (Agent Workflow), Activity (Agent Calls), Server (Render Offload), ThumbsUp (Agent Score), Gauge (Token Usage), Puzzle (Plugins), Route (Models and Routing). The label choice uses the shared browser key, so it follows the other rails. The rail markup is repeated from `Pricing.tsx` rather than extracted into a component: two pages, and the project rule is no new abstractions without need.
- **Bodies, not rewrites.** Each page keeps its default export and logic; the outer `Page` and its page `h1` go (the page heading is "AI & Agent Settings"), and the loading/error returns become plain fragments instead of nested `Page`s. Models' second heading "Generation and budgets" becomes an `h2` so the page has one `h1`. Only the chosen tab is mounted, so a tab's queries run when it is opened, as today. Their existing tests render the components directly and keep passing unchanged (none looks for the dropped `h1`; checked).

## Risks / Trade-offs

- [The first developer nav entry was Models; the default tab is now Memory] → follows the owner's order.
- ["Models and Routing" is longer than the shared rail is wide] → its label wraps onto two lines within the 40 px row; the rail width is not changed, since the conversation's flyouts are placed against it.
- [The redirect re-runs the session check, as seen in combine-pricing-pages] → tests use the new addresses where they exercise the page itself.
