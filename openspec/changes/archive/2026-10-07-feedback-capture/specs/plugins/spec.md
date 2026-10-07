## MODIFIED Requirements

### Requirement: Every tool comes from a plugin manifest
Each plugin SHALL be a folder under `backend/plugins/` holding a `manifest.yaml` with its name, description, kind (`builtin` or `https`), the agent role it serves, the tools it provides, whether it is enabled by default and whether the homeowner may toggle it. A built-in manifest MAY also name other agents that share its tools (`also_for`), never repeating an agent or naming its own role. The backend SHALL load every manifest at startup and SHALL fail startup naming the file for a missing field, an unknown field, a tool named by two plugins, a built-in tool with no implementation, an unknown role or an invalid `also_for`. The set of tools agents may name SHALL be exactly the tools the manifests declare, and an agent's instruction file MAY name a tool only when the agent is the plugin's role or is named in its `also_for`.

#### Scenario: Ten toggleable tools
- **WHEN** the service starts with the shipped plugins
- **THEN** the loaded plugins provide at least ten tools the homeowner can toggle

#### Scenario: Two plugins claim a tool
- **WHEN** two manifests both declare `cut_list`
- **THEN** startup fails naming both files

#### Scenario: A tool shared by two agents
- **WHEN** the `render_feedback` manifest serves the builder and names `lighting` in `also_for`
- **THEN** both `builder.md` and `lighting.md` may name `record_render_feedback`, and `reviewer.md` naming it fails startup naming the file and the tool

#### Scenario: A manifest shares a tool with its own role
- **WHEN** a manifest with role `builder` lists `builder` in `also_for`
- **THEN** startup fails naming the manifest file and `also_for`
