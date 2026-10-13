## MODIFIED Requirements

### Requirement: Kitchen safety gates keep capacity NOT VERIFIED without verified inputs
Kitchen replies SHALL require verified panel grade/thickness, span/support, joint load path, moisture environment and tipping/stability inputs for cabinets; exact runner series/variant and mounting for drawers; substrate/anchors for wall units; door mass/dimensions and manufacturer mounting for hinges; P2-versus-humid board distinction and sealed edges for moisture; exact appliance model/manual for clearances; and exact worktop product instructions for overhangs/cutouts. DIN EN 15939 SHALL NOT be treated as wall-fixing verification. DIN EN 14749 compliance SHALL NOT be asserted without documented applicable tests. Missing inputs SHALL yield the short not-verified status of the homeowner chat; the chat reply SHALL NOT list the missing inputs. Deterministic calculator families already registered SHALL be reused; unavailable or unreviewed methods SHALL remain not verified.

#### Scenario: 18 mm P2 kitchen shelf without load data
- **WHEN** the owner asks whether 18 mm P2 suits a 900 mm kitchen shelf without load, depth, supports or verified E/strength
- **THEN** the reply shows the short not-verified status and does not claim adequacy

#### Scenario: Integrated oven clearance without model
- **WHEN** the owner asks what gap an integrated oven needs without naming the appliance model
- **THEN** the reply shows the short not-verified status and states no clearance

#### Scenario: DIN EN 14749 compliance asked without tests
- **WHEN** the owner asks whether DIN EN 14749 compliance is confirmed
- **THEN** the reply shows the short not-verified status and does not assert compliance
