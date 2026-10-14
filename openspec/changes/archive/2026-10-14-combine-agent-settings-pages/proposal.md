## Why

The developer navigation has eleven entries; eight of them — Models, Plugins, Usage, Feedback, Offload, Calls, Workflow and Memory — are settings and readings about the agents and their models. The owner asked (2026-10-14) to combine those eight into one "AI & Agent Settings" page with a tab each, under clearer names.

## What Changes

- A new **AI & Agent Settings** developer page at `/admin/agents` with eight tabs, in the order the owner listed them: **Agent Memory** (was Memory), **Agent Workflow** (was Workflow), **Agent Calls** (was Calls), **Render Offload** (was Offload), **Agent Score** (was Feedback), **Token Usage** (was Usage), **Plugins**, **Models and Routing** (was Models). Agent Memory is chosen first. The tabs are a rail at the screen's left edge with the same font, icon style, colours and "Hide labels" switch as the conversation page's panel rail and the Pricing Overview rail; the label choice is shared with them.
- Each tab has its own address (`/admin/agents/memory`, `/workflow`, `/calls`, `/offload`, `/score`, `/usage`, `/plugins`, `/models`); `/admin/agents` and an unknown tab open Agent Memory.
- The old page addresses `/admin/memory`, `/admin/workflow`, `/admin/conversations`, `/admin/offload`, `/admin/feedback`, `/admin/usage`, `/admin/plugins` and `/admin/models` open their tab, so bookmarks keep working.
- The developer navigation shows one "AI & Agent Settings" entry, where "Models" stood, in place of the eight; Guidelines, Knowledge and Rules keep their own entries.
- Not changed: every API route, form, table, graph, refusal and query key on the eight pages. Only where they are shown and what they are called changes. The developer gate is unchanged.

Ladder step and agents: none — developer UI only; no agent, prompt, tool, routing or generator is touched. The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

### Modified Capabilities
- `dev-panel`: the eight developer pages become tabs of one AI & Agent Settings page.

## Impact

Frontend only: a new `frontend/src/routes/admin/AgentSettings.tsx`; `Memory.tsx`, `Workflow.tsx`, `ConversationCalls.tsx`, `Offload.tsx`, `Feedback.tsx`, `Usage.tsx`, `Plugins.tsx` and `Models.tsx` lose their `Page` wrapper and page `h1` and become tab bodies; `frontend/src/App.tsx` (nav entry, routes, redirects); tests in `App.test.tsx` and a new `AgentSettings.test.tsx`. `/admin` is already proxied as a page path in `vite.config.ts`, so no proxy change. No backend, schema, migration or API change.
No task renders; no tier is used.
