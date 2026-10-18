## MODIFIED Requirements

### Requirement: Every tool comes from a plugin manifest
Each plugin SHALL be a folder under `backend/plugins/` holding a `manifest.yaml` with its name, description, kind (`builtin` or `https`), the agent role it serves, the tools it provides, whether it is enabled by default and whether it is marked toggleable. The toggleable mark SHALL be kept in manifests and shown on the developer's Plugins page, and SHALL have no effect on which tools are bound. A built-in manifest MAY also name other agents that share its tools (`also_for`), never repeating an agent or naming its own role. The backend SHALL load every manifest at startup and SHALL fail startup naming the file for a missing field, an unknown field, a tool named by two plugins, a built-in tool with no implementation, an unknown role or an invalid `also_for`. The set of tools agents may name SHALL be exactly the tools the manifests declare, and an agent's instruction file MAY name a tool only when the agent is the plugin's role or is named in its `also_for`.

#### Scenario: Ten toggleable tools
- **WHEN** the service starts with the shipped plugins
- **THEN** the loaded plugins provide at least ten tools that the developer can enable or disable on the Plugins page

#### Scenario: Two plugins claim a tool
- **WHEN** two manifests both declare `cut_list`
- **THEN** startup fails naming both files

#### Scenario: A tool shared by two agents
- **WHEN** the `render_feedback` manifest serves the builder and names `lighting` in `also_for`
- **THEN** both `builder.md` and `lighting.md` may name `record_render_feedback`, and `reviewer.md` naming it fails startup naming the file and the tool

#### Scenario: A manifest shares a tool with its own role
- **WHEN** a manifest with role `builder` lists `builder` in `also_for`
- **THEN** startup fails naming the manifest file and `also_for`

## ADDED Requirements

### Requirement: Plugins are enabled globally
The developer SHALL be able to enable or disable a plugin for the whole service from the Plugins page. A tool SHALL be bound to a specialist only when its plugin is globally enabled and the specialist's instruction header names it, or, for an HTTPS plugin, when its role is that specialist. No per-conversation setting SHALL change which tools are bound. A plugin that is disabled by default (such as `engineering_knowledge`) SHALL stay unbound in every conversation until the developer enables it.

#### Scenario: Disabled for every conversation
- **WHEN** the developer disables `room_fit` on the Plugins page
- **THEN** the Designer binds no `room_fit` in any conversation from the next turn

#### Scenario: Default off
- **WHEN** `engineering_knowledge` is disabled by default and the developer has not enabled it
- **THEN** no conversation binds its tools

## REMOVED Requirements

### Requirement: Plugins are enabled globally and per conversation
**Reason**: Per-conversation switches are dropped (owner decision of 2026-10-18). Replaced by "Plugins are enabled globally".
**Migration**: Enable or disable plugins on `/admin/plugins`. Per-thread settings are dropped.
