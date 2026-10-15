## Purpose

Defines the information and mandatory limitations in furniture engineering answers, keeping retrieved evidence and visual design approval separate from verified calculations or conformity.

## ADDED Requirements

### Requirement: Engineering replies show evidence and verification limitations
An engineering reply SHALL identify assumptions, supplied loads/dimensions, exact product/grade when known, source plus page/section, warnings and missing inputs. Its claim/status envelope SHALL be validated by application code; model-authored text SHALL NOT set verification or conformity status or invent a property. With no enabled calculation method, the reply SHALL state that calculation is not implemented and label capacity/safety conclusions `NOT VERIFIED`. Retrieval relevance, design approval, build success, drilling completeness and a render SHALL NOT imply tested/certified conformity.

#### Scenario: Load capacity asked during foundation phase
- **WHEN** the owner asks whether a shelf can hold 30 kg
- **THEN** the reply states which inputs/evidence are known, lists what is missing and says load capacity is NOT VERIFIED because numerical engineering calculation is not implemented

#### Scenario: Invalid model claim
- **WHEN** a model supplies an unsupported verified-capacity or conformity claim
- **THEN** validation rejects it and the displayed reply uses a fixed insufficient-evidence/NOT VERIFIED status

### Requirement: Missing engineering inputs are never defaulted into safety
Material grade, load, support geometry, duration and verified capacity needed for a check SHALL NOT be inferred from a generic material name, appearance or another model. Missing inputs SHALL produce questions or `NOT VERIFIED`. Legal/standard applicability SHALL be explicit per project; an indexed DIN edition SHALL NOT automatically be treated as law, and Berlin building rules SHALL NOT automatically be applied to all freestanding furniture.

#### Scenario: Board known by thickness only
- **WHEN** a shelf is specified as an 18 mm board without grade and load conditions
- **THEN** the reply asks for the missing data or reports NOT VERIFIED rather than assigning a safe span

#### Scenario: Link-only standard
- **WHEN** only a standard's title and URL are available
- **THEN** the reply cites it as metadata and does not claim to have checked its clauses or establish conformity

### Requirement: Higher-risk furniture retains mandatory safety gates
Murphy-bed final safe-to-build/anchor determinations SHALL require a verified matching manufacturer manual, complete wall/anchor assessment and appropriate qualified review, including crush/impact/unintended deployment risks. Wall cabinets/heavy shelves SHALL require substrate, fixing geometry and load transfer; hanger ratings SHALL NOT establish wall-anchor resistance. Entertainment-unit evidence SHALL address tipping, TV loads and foreseeable child climbing. Countertop advice SHALL use exact material/product/thickness support, cutout and overhang instructions and SHALL NOT extrapolate between stone/material types. Missing gates SHALL yield `NOT VERIFIED` rather than final safety approval.

#### Scenario: Hanger rating without wall data
- **WHEN** the owner supplies a cabinet-hanger rating but no substrate/anchor information
- **THEN** wall fixing stays NOT VERIFIED and the missing wall/fixing data are named

#### Scenario: Murphy bed lacks matching manual
- **WHEN** the available manual names a different Murphy-bed mechanism revision
- **THEN** the reply requests the matching manual and qualified review and provides no final safe-to-build determination

#### Scenario: TV unit ignores child climbing
- **WHEN** an entertainment-unit discussion has only the unloaded cabinet dimensions
- **THEN** the reply identifies TV and foreseeable misuse/tipping inputs as unresolved

#### Scenario: Countertop product mismatch
- **WHEN** only a quartz support limit is available for a ceramic countertop
- **THEN** that limit is not applied to the ceramic product and support verification stays incomplete

### Requirement: Preliminary geometry remains separate from engineering status
An incomplete engineering assessment SHALL NOT alone prevent creating, revising or rendering a valid preliminary design through the existing confirmation and render guards. The displayed engineering status SHALL remain unverified. Source evidence SHALL NOT write dimensions, approve a piece or authorise installation.

#### Scenario: Owner continues a preliminary design
- **WHEN** the owner confirms a valid dimensional revision while load capacity remains unverified
- **THEN** the normal revision proceeds and no engineering verification or installation approval is recorded
