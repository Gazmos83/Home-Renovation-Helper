# plugins Specification

## Purpose

Defines tools as plugins: the manifest every plugin folder carries, the two kinds (built-in and declarative HTTPS), how they are loaded and validated, how an HTTPS plugin is executed safely, and how plugins are enabled globally and per conversation.

## Requirements

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

### Requirement: An HTTPS plugin is declarative and fenced
An `https` manifest SHALL declare an input schema (primitive or array-of-primitive properties, no additional properties), an output schema, and one GET request whose URL is https on a host in the configured allow-list, with no credentials, port, query string or fragment, and whose path placeholders each name a declared non-array input. A manifest using any other construct SHALL be refused naming the field. No HTTPS plugin SHALL be enabled by default.

#### Scenario: Host not allowed
- **WHEN** an HTTPS manifest's URL host is not in the allow-list
- **THEN** startup fails naming the manifest and the host

### Requirement: An HTTPS call cannot reach private addresses or run unbounded
Executing an HTTPS plugin SHALL re-validate the arguments, re-check the host against the allow-list, resolve it and refuse any address that is not globally routable, connect to the checked address with the host's name for TLS, follow no redirect, stop reading past the response cap, time out at the configured limit, and pace calls per host. The output SHALL be validated against the output schema with undeclared fields dropped and SHALL reach the model only as delimited untrusted content. Every call SHALL be recorded with its plugin, thread, outcome and duration, never its arguments or body; a failure SHALL come back to the agent as a stated inability, never ending the turn.

#### Scenario: Host resolves to a private address
- **WHEN** an allow-listed host resolves to 10.0.0.5
- **THEN** no connection is made, the agent is told the call was refused, and the invocation is recorded as refused

#### Scenario: Redirect
- **WHEN** the response is a redirect
- **THEN** it is not followed and the call is recorded as refused

### Requirement: Plugins are enabled globally
The developer SHALL be able to enable or disable a plugin for the whole service from the Plugins page. A tool SHALL be bound to a specialist only when its plugin is globally enabled and the specialist's instruction header names it, or, for an HTTPS plugin, when its role is that specialist. No per-conversation setting SHALL change which tools are bound. A plugin that is disabled by default (such as `engineering_knowledge`) SHALL stay unbound in every conversation until the developer enables it.

#### Scenario: Disabled for every conversation
- **WHEN** the developer disables `room_fit` on the Plugins page
- **THEN** the Designer binds no `room_fit` in any conversation from the next turn

#### Scenario: Default off
- **WHEN** `engineering_knowledge` is disabled by default and the developer has not enabled it
- **THEN** no conversation binds its tools
