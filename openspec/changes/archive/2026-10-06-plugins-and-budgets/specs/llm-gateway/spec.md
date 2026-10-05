## MODIFIED Requirements

### Requirement: Per-model generation profile
Each registry slug SHALL have a generation profile (temperature where the model supports it, maximum output tokens bounded by the model's limit and an application ceiling) that is applied to every call for that slug and defaults to the gateway's own values when unset. The developer panel edits and resets profiles; an edit SHALL apply to the next call without a restart.

#### Scenario: Default profile
- **WHEN** no profile has been stored for a slug
- **THEN** calls for that slug send neither temperature nor an output cap

#### Scenario: Temperature on an unsupported model
- **WHEN** a profile with a temperature is applied to a slug that does not support temperature
- **THEN** the call omits temperature and keeps the other profile values

#### Scenario: Edited without restart
- **WHEN** the developer sets a slug's output cap to 2048
- **THEN** the next call for that slug sends `max_tokens` 2048
