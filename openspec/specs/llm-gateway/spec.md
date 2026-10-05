## Purpose

Defines how the application reaches language models: one gateway and one credential, a closed registry of probed models, a per-agent routing file with no backup slot, a startup probe that turns a gateway block into a named configuration error, and the credential kept out of everything an agent can see.

## Requirements

### Requirement: One gateway, one credential
The application SHALL route every language-model call through the OpenRouter gateway with one credential read from configuration, SHALL NOT hold a credential issued by an individual model vendor, and SHALL refuse to start when the gateway credential is absent.

#### Scenario: Credential missing
- **WHEN** the service starts without the gateway credential
- **THEN** startup fails with an error naming `OPENROUTER_API_KEY`

#### Scenario: Ambient vendor credential ignored
- **WHEN** a vendor's own API-key variable is present in the environment
- **THEN** the gateway client is built from the configured gateway credential only

### Requirement: Closed model registry
The application SHALL maintain a registry of known model slugs, each with a display name, context window, output-token limit, image-input support, temperature support and the date it was probed. A slug outside the registry SHALL be refused by name wherever a model is chosen.

#### Scenario: Registry contents
- **WHEN** the registry is listed
- **THEN** it contains exactly the slugs approved in the build guide, each with the attributes above, and no price fields

#### Scenario: Unknown slug refused
- **WHEN** a configuration names a slug the registry does not know
- **THEN** startup fails with an error quoting the slug and listing the known slugs

### Requirement: Per-agent routing from a configuration file
The application SHALL read a routing file mapping each agent slot (Foreman, Intake, Designer, Builder, Lighting, Reviewer, Researcher) to exactly one registry slug. The file SHALL NOT define a backup or fallback slug. A missing slot, an unknown slug, a slot whose agent needs image input routed to a text-only model, or a duplicate slot SHALL fail startup by name.

#### Scenario: Complete routing file
- **WHEN** the routing file maps every slot to a known slug
- **THEN** the service starts and the startup summary lists each slot with its slug

#### Scenario: Slot missing
- **WHEN** the routing file omits the Reviewer slot
- **THEN** startup fails with an error naming `reviewer`

#### Scenario: Reviewer routed to a text-only model
- **WHEN** the routing file maps the Reviewer to a registry slug without image input
- **THEN** startup fails with an error naming the slot and the slug

#### Scenario: Fallback key present
- **WHEN** the routing file carries a backup or fallback key for any slot
- **THEN** startup fails with an error naming the unsupported key

### Requirement: Startup probe of routed models
At startup the application SHALL send one minimal request through the gateway for each distinct routed slug and SHALL report a refusal, a guardrail block or an unlisted model as a configuration error naming the slug. The probe MAY be disabled by configuration for offline tests, in which case the startup summary SHALL say the probe was skipped.

#### Scenario: All routed models answer
- **WHEN** every distinct routed slug answers the probe
- **THEN** the service starts and the summary records each slug as probed

#### Scenario: Guardrail block
- **WHEN** the gateway refuses a routed slug with a policy or guardrail response
- **THEN** startup fails with a configuration error naming the slug and the gateway's stated reason, not a generic model failure

#### Scenario: Probe disabled
- **WHEN** the probe is disabled by configuration
- **THEN** the service starts without contacting the gateway and the summary states the probe was skipped

### Requirement: Routed providers must support the parameters sent
Every gateway request SHALL require the serving provider to support the parameters and tools it carries, so a request is never silently served by a provider that ignores part of it.

#### Scenario: Provider routing on the wire
- **WHEN** any model call is issued
- **THEN** the request body asks the gateway to require parameter support from the provider

### Requirement: Credential exclusion
The gateway credential SHALL NOT appear in graph state, in any prompt, in any tool result, in a log record, in a trace, or in a response to a caller.

#### Scenario: Error path carries no credential
- **WHEN** a gateway call fails and the failure is logged and returned
- **THEN** neither the log record nor the response contains the credential or the raw provider payload

### Requirement: Gateway failure is a stated inability
A refusal, timeout, rate limit, authorisation error or transport failure at the gateway SHALL be classified and surfaced as a stated inability to answer, distinguishable from an answer, and recorded in the structured logs.

#### Scenario: Gateway timeout
- **WHEN** the gateway does not answer within the configured timeout
- **THEN** the caller receives a stated failure of class timeout and a structured log record names the operation and class

#### Scenario: Rate limited
- **WHEN** the gateway answers with a rate-limit status
- **THEN** the caller receives a stated failure of class rate-limited, without the provider's body

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
