## ADDED Requirements

### Requirement: The developer panel has an Offload page
The developer route tree SHALL include an Offload page showing the configuration summary, a connection-test button with its result, the remote benchmark with its last value and time, the final-target switch, the hourly rate, and the recent remote jobs. Like the other developer pages, it SHALL be reachable only when the developer API answers, SHALL show an API refusal next to the field it names, and SHALL pass a recorded browser check before it counts as done. No homeowner page SHALL show the host, the target setting or a euro figure.

#### Scenario: Target refused on the page
- **WHEN** the developer switches finals to `remote` while offload is not configured
- **THEN** the page shows the refusal next to the target switch and the switch stays on `local`
