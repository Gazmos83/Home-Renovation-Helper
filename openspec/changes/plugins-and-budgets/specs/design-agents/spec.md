## MODIFIED Requirements

### Requirement: Each specialist runs on its routed model with its instruction file
Each specialist SHALL call the model routed for its slot (`intake`, `designer`, `builder`, `researcher`, `reviewer`; the Foreman on `foreman`) with that slot's generation profile, and SHALL be prompted from its checked-in instruction file: a header naming its tools (not editable) and text, followed by the fixed notes and the untrusted-content guard composed by code, exactly once and last. The tools a header may name SHALL be the tools the plugin manifests declare, and a specialist SHALL bind only the named tools whose plugin is enabled for the thread, plus enabled HTTPS plugins for its role. A missing or malformed instruction file SHALL stop startup naming the file.

#### Scenario: Prompt shape
- **WHEN** the Designer's prompt is assembled
- **THEN** it ends with the untrusted-content guard, contains it once, and binds exactly the tools its header names that are enabled for the thread

#### Scenario: Instruction file missing
- **WHEN** `reviewer.md` is absent
- **THEN** startup fails naming `reviewer.md`

#### Scenario: Header names an undeclared tool
- **WHEN** `designer.md` names a tool no manifest declares
- **THEN** startup fails naming `designer.md` and the tool
