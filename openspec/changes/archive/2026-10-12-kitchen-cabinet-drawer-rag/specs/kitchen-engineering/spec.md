## Purpose

Extends the existing furniture-engineering knowledge store with kitchen cabinet and drawer namespaces, licence-gated source metadata, intent routing and safety validation rules without replacing the RAG pipeline.

## ADDED Requirements

### Requirement: Kitchen namespaces coexist with existing collections
The engineering catalogue SHALL support the logical collections `kitchen_cabinet_engineering`, `kitchen_drawer_systems`, `kitchen_hinges_hardware`, `kitchen_panel_materials`, `kitchen_cabinet_connections`, `kitchen_wall_anchoring`, `kitchen_ergonomics_accessibility`, `kitchen_moisture_protection`, `kitchen_appliance_integration` and `kitchen_structural_validation` in addition to the existing seven collections. Overlapping kitchen sources SHALL also remain tagged on equivalent existing collections where applicable. Existing collection identifiers and published embeddings SHALL remain unchanged. Unknown metadata fields on legacy versions SHALL stay null.

#### Scenario: Dual-tagged manufacturer index
- **WHEN** a Blum catalogue index is registered for kitchen drawers and hinges
- **THEN** it is listable under the kitchen drawer/hinge namespaces and under `hardware_manuals`, with no extracted passage unless rights already permit content

#### Scenario: Legacy material source still searchable
- **WHEN** an existing `material_datasheets` source is queried after kitchen namespaces are added
- **THEN** it remains findable by its original collection filter and identity

### Requirement: Kitchen catalogue entries default to link-only
Kitchen DIN/EN candidates, manufacturer indexes and appliance/worktop placeholders SHALL register as metadata and official URLs only until a documented rights decision permits extraction and embedding. Registration alone SHALL NOT download, extract or embed content. An explicit embedding-approval flag on metadata SHALL remain false unless a current rights grant covers local embedding for that version.

#### Scenario: Licensed DIN remains metadata-only
- **WHEN** DIN EN 14749 or DIN EN 312 is seeded without rights approval
- **THEN** only identity, edition when known and URL are stored, and no engineering chunk or vector is created

#### Scenario: Copyrighted PDF is not ingested from a public link
- **WHEN** a caller attempts full-text ingestion of a copyrighted DIN PDF without documented permission
- **THEN** the licence gate refuses embedding and the source stays metadata-only

### Requirement: Kitchen product constraints stay null until verified
Structured kitchen product fields (manufacturer, exact model, part number, variant, nominal load, runner length, door mass/height, panel thickness and mounting conditions) SHALL accept nulls. Numerical engineering values SHALL NOT be filled from generic assumptions or model-generated numbers. Cross-manufacturer substitution of ratings SHALL be refused.

#### Scenario: Runner rating without exact model
- **WHEN** the owner asks whether a 40 kg rated runner holds a 40 kg kitchen drawer without naming the exact series/variant
- **THEN** the reply reports NOT VERIFIED and names the missing exact model, rating conditions, drawer self-weight and box/cabinet support

#### Scenario: Cross-manufacturer runner data refused
- **WHEN** a query asks to apply Blum capacity data to a Hettich runner
- **THEN** the system refuses the substitution and requires the exact Hettich part evidence

### Requirement: Kitchen intents route to kitchen and related existing evidence
Kitchen design questions about base/wall/tall cabinets, sink units, drawers, hinges, hangers/anchors, moisture, appliances, ergonomics or worktops SHALL route retrieval toward the relevant kitchen namespaces and the related existing collections (`material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety`, `engineering_fundamentals` and structural calculation resources). Jurisdiction filters for DE/EU SHALL apply where relevant. Evidence priority SHALL remain: applicable law, licensed applicable standard, exact manufacturer manual, validated calculation, then general guidance.

#### Scenario: Wall-cabinet anchoring query
- **WHEN** the owner asks how many anchors a 1200 mm wall cabinet needs on plasterboard
- **THEN** retrieval targets wall-anchoring and related hardware/standards evidence, and the reply requires substrate and verified fixing specification rather than inventing an anchor count

#### Scenario: Ordinary non-kitchen engineering query still works
- **WHEN** an existing Murphy-bed or generic shelf engineering question is asked after the kitchen extension
- **THEN** previous routing and missing-input gates continue to apply

### Requirement: Kitchen safety gates keep capacity NOT VERIFIED without verified inputs
Kitchen replies SHALL require verified panel grade/thickness, span/support, joint load path, moisture environment and tipping/stability inputs for cabinets; exact runner series/variant and mounting for drawers; substrate/anchors for wall units; door mass/dimensions and manufacturer mounting for hinges; P2-versus-humid board distinction and sealed edges for moisture; exact appliance model/manual for clearances; and exact worktop product instructions for overhangs/cutouts. DIN EN 15939 SHALL NOT be treated as wall-fixing verification. DIN EN 14749 compliance SHALL NOT be asserted without documented applicable tests. Missing inputs SHALL yield `NOT VERIFIED`. Deterministic calculator families already registered SHALL be reused; unavailable or unreviewed methods SHALL remain `NOT VERIFIED`.

#### Scenario: 18 mm P2 kitchen shelf without load data
- **WHEN** the owner asks whether 18 mm P2 suits a 900 mm kitchen shelf without load, depth, supports or verified E/strength
- **THEN** the reply asks for those inputs or reports NOT VERIFIED and does not claim adequacy

#### Scenario: Integrated oven clearance without model
- **WHEN** the owner asks what gap an integrated oven needs without naming the appliance model
- **THEN** the reply requires the exact manufacturer installation manual before stating a clearance

#### Scenario: DIN EN 14749 compliance asked without tests
- **WHEN** the owner asks whether DIN EN 14749 compliance is confirmed
- **THEN** the reply does not assert compliance and states that indexed standards are not proof of conformity
