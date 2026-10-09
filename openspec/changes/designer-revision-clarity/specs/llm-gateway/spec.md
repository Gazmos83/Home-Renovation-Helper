## MODIFIED Requirements

### Requirement: Closed model registry
The application SHALL maintain a registry of known model slugs, each with a display name, context window, output-token limit, image-input support, temperature support and the date it was probed. A slug outside the registry SHALL be refused by name wherever a model is chosen. An entry whose slug is a gateway alias, one the gateway redirects to the newest model of a family, SHALL be marked as an alias. The developer panel SHALL show that mark, so the owner can see that the model behind the slug may change without a new probe.

#### Scenario: Registry contents
- **WHEN** the registry is listed
- **THEN** it contains exactly the slugs approved in the build guide, each with the attributes above, and no price fields

#### Scenario: Unknown slug refused
- **WHEN** a configuration names a slug the registry does not know
- **THEN** startup fails with an error quoting the slug and listing the known slugs

#### Scenario: V4 Flash entries
- **WHEN** the registry is listed
- **THEN** it includes `deepseek/deepseek-v4-flash` and `~deepseek/deepseek-v4-flash-latest` as available and text-only, each with the date of its own probe, the second marked as an alias and the first not

#### Scenario: Alias shown in the developer panel
- **WHEN** the owner opens the model list in the developer panel
- **THEN** `~deepseek/deepseek-v4-flash-latest` is shown as an alias, and `deepseek/deepseek-v4-flash` is not

#### Scenario: V4 Flash kept from image slots
- **WHEN** Intake or the Reviewer is routed to either V4 Flash entry, from the routing file or the developer panel
- **THEN** the routing is refused naming the slot and that the model is text-only, and no image is sent to the model

### Requirement: Per-agent routing from a configuration file
The application SHALL read a routing file mapping each agent slot (Foreman, Intake, Designer, Builder, Lighting, Reviewer, Researcher) to exactly one registry slug. The file SHALL NOT define a backup or fallback slug. The slots whose agent needs image input are Intake (blueprints and photos) and the Reviewer (renders). A missing slot, an unknown slug, a slot whose agent needs image input routed to a text-only model, or a duplicate slot SHALL fail startup by name. The shipped routing file SHALL route the Foreman and the Designer to `~deepseek/deepseek-v4-flash-latest`. A routing override saved from the developer panel SHALL still take precedence over the file.

#### Scenario: Complete routing file
- **WHEN** the routing file maps every slot to a known slug
- **THEN** the service starts and the startup summary lists each slot with its slug

#### Scenario: Slot missing
- **WHEN** the routing file omits the Reviewer slot
- **THEN** startup fails with an error naming `reviewer`

#### Scenario: Reviewer routed to a text-only model
- **WHEN** the routing file maps the Reviewer to a registry slug without image input
- **THEN** startup fails with an error naming the slot and the slug

#### Scenario: Intake routed to a text-only model
- **WHEN** the routing file maps Intake to a registry slug without image input
- **THEN** startup fails with an error naming `intake` and the slug

#### Scenario: Fallback key present
- **WHEN** the routing file carries a backup or fallback key for any slot
- **THEN** startup fails with an error naming the unsupported key

#### Scenario: Shipped defaults for the Foreman and the Designer
- **WHEN** no routing override is saved for the Foreman or the Designer
- **THEN** both slots run on `~deepseek/deepseek-v4-flash-latest`, and the startup probe sends it one text request

#### Scenario: Saved override still wins
- **WHEN** a `routing:designer` override names `deepseek/deepseek-v4.1-flash`
- **THEN** the Designer runs on `deepseek/deepseek-v4.1-flash` until the owner resets or changes that override in the developer panel
