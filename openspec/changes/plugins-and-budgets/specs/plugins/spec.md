## Purpose

Defines tools as plugins: the manifest every plugin folder carries, the two kinds (built-in and declarative HTTPS), how they are loaded and validated, how an HTTPS plugin is executed safely, and how plugins are enabled globally and per conversation.

## ADDED Requirements

### Requirement: Every tool comes from a plugin manifest
Each plugin SHALL be a folder under `backend/plugins/` holding a `manifest.yaml` with its name, description, kind (`builtin` or `https`), the agent role it serves, the tools it provides, whether it is enabled by default and whether the homeowner may toggle it. The backend SHALL load every manifest at startup and SHALL fail startup naming the file for a missing field, an unknown field, a tool named by two plugins, a built-in tool with no implementation, or an unknown role. The set of tools agents may name SHALL be exactly the tools the manifests declare.

#### Scenario: Ten toggleable tools
- **WHEN** the service starts with the shipped plugins
- **THEN** the loaded plugins provide at least ten tools the homeowner can toggle

#### Scenario: Two plugins claim a tool
- **WHEN** two manifests both declare `cut_list`
- **THEN** startup fails naming both files

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

### Requirement: Plugins are enabled globally and per conversation
The developer SHALL be able to enable or disable a plugin for the whole service; the homeowner SHALL be able to switch each toggleable, globally enabled plugin on or off for one conversation, starting from the manifest's default. A tool SHALL be bound to a specialist only when its plugin is globally enabled, enabled for the thread (or not toggleable), and the specialist's instruction header names it — or, for an HTTPS plugin, its role is that specialist.

#### Scenario: Toggled off in one thread
- **WHEN** the owner switches `room_fit` off in one conversation
- **THEN** the Designer in that conversation binds no `room_fit`, and in another conversation still does

#### Scenario: Not toggleable
- **WHEN** the owner tries to switch off `create_piece`
- **THEN** it is refused naming the plugin as not toggleable
