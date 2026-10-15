## MODIFIED Requirements

### Requirement: Only finals offload, and only when chosen
Only `final` renders SHALL run remotely, and only when offload is configured and the developer has set the final target to `remote`. The default target SHALL be `local`. Draft renders (including restyles), builds, screenshots and the local benchmark SHALL always run locally. A detail turntable SHALL run only remotely; with the target `local` it SHALL be refused, never run on the laptop.

#### Scenario: Draft with target remote
- **WHEN** the target is `remote` and a `draft` turntable is requested
- **THEN** it runs on the laptop

#### Scenario: Final with target remote
- **WHEN** the target is `remote` and the owner approves a `final` turntable
- **THEN** it runs on the render server

#### Scenario: Detail turntable with target local
- **WHEN** the target is `local` and a `final` detail turntable is requested
- **THEN** it is refused saying a detail turntable runs only on the render server, and nothing runs on the laptop
