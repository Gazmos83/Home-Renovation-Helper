## MODIFIED Requirements

### Requirement: Only finals offload, and only when chosen
Only `final` renders SHALL run remotely, and only when offload is configured and the developer has set the final target to `remote`. The default target SHALL be `local`. Draft renders (including restyles), builds, screenshots and the local benchmark SHALL always run locally. A detail still or turntable SHALL run where finals run, like any `final`.

#### Scenario: Draft with target remote
- **WHEN** the target is `remote` and a `draft` turntable is requested
- **THEN** it runs on the laptop

#### Scenario: Final with target remote
- **WHEN** the target is `remote` and the owner approves a `final` turntable
- **THEN** it runs on the render server

#### Scenario: Detail turntable with target local
- **WHEN** the target is `local` and the owner approves a `final` detail turntable after its long-render warning
- **THEN** it runs on the laptop and nothing is sent to the render server
