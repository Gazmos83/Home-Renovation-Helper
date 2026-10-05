## MODIFIED Requirements

### Requirement: Per-agent routing from a configuration file
The application SHALL read a routing file mapping each agent slot (Foreman, Intake, Designer, Builder, Lighting, Reviewer, Researcher) to exactly one registry slug. The file SHALL NOT define a backup or fallback slug. The slots whose agent needs image input are Intake (blueprints and photos) and the Reviewer (renders). A missing slot, an unknown slug, a slot whose agent needs image input routed to a text-only model, or a duplicate slot SHALL fail startup by name.

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
