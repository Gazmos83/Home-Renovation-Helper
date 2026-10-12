## Purpose

Defines bounded, deterministic furniture engineering calculations with reviewed methods, verified unit-aware evidence and reproducible reports that cannot imply whole-design safety or certification.

## ADDED Requirements

### Requirement: Only reviewed bounded methods can calculate verification results
The calculator registry SHALL define method/version, cited equation/criterion, mandatory inputs/units, supported geometry/load/environment cases, reviewed acceptance criteria and independently checked reference cases. Methods SHALL cover bounded bending/deflection, creep, joint resistance, exact hardware capacity, anchorage and tipping cases, with product-specific countertop instruction checks. A method SHALL remain unavailable until qualified review of its scope/references. No caller/model expression or code SHALL be evaluated. Unsupported cases SHALL return `NOT VERIFIED`, not a guessed simplification.

#### Scenario: Method awaits review
- **WHEN** a bending method has been implemented but its reference cases have not passed qualified review
- **THEN** it cannot return a verification result and reports method unavailable/NOT VERIFIED

#### Scenario: Folded shelf unsupported
- **WHEN** a rectangular shelf method receives compound folded or polygonal geometry outside its reviewed scope
- **THEN** it reports NOT VERIFIED and does not replace that geometry with an assumed rectangular span

#### Scenario: New formula version
- **WHEN** a reviewed method's formula or acceptance criterion changes
- **THEN** subsequent results identify a new method version and existing reports remain unchanged

### Requirement: Assessment inputs bind exact geometry and reviewed evidence
An assessment SHALL identify an exact stored piece/spec version and relevant parts, explicit product/grade/property revisions, hardware/manual revisions, loads, support geometry and installation/environment/duration facts. Geometry SHALL come from that stored spec and deterministic derivation. Assumed user facts SHALL be labelled; storing new assessment facts/bindings SHALL require owner confirmation. A material display name, board thickness, cited drilling sheet or mean test property SHALL NOT alone establish allowable resistance or support behaviour.

#### Scenario: Material slot is only a name
- **WHEN** a piece says "oak" with thickness but has no verified grade/product binding
- **THEN** the calculation reports the missing binding rather than assigning generic wood properties

#### Scenario: Assessment inputs declined
- **WHEN** the owner declines proposed loads/support facts
- **THEN** they are not recorded as confirmed and no calculation uses them as verified inputs

#### Scenario: Divider attachment insufficient
- **WHEN** a partial divider sits on a fixed shelf but no reviewed support/joint path is identified
- **THEN** it is not automatically treated as a structural support splitting the span

### Requirement: Units ranges and conditions are validated before computation
Calculations SHALL distinguish mm/m, kg, N/kN, MPa and distributed-load units; mass-to-force conversion SHALL use `F_N = mass_kg × 9.81` explicitly. Inputs SHALL be finite and physically valid for the method. Source ranges SHALL remain ranges unless the method defines reviewed bound propagation; their midpoint SHALL NOT be assumed. Missing/unverified grade, load, supports, duration, capacity or acceptance criteria SHALL result in `NOT VERIFIED`; calculated values unavailable for that check SHALL be null rather than zero.

#### Scenario: Mass converted explicitly
- **WHEN** a reviewed case supplies 10 kg as a mass input requiring force
- **THEN** its force input is 98.1 N with the conversion recorded, not 10 N

#### Scenario: Invalid number
- **WHEN** an input is non-finite or a required span/section dimension is non-positive
- **THEN** validation refuses it naming the input before arithmetic

#### Scenario: Creep duration unknown
- **WHEN** an immediate-deflection calculation has verified inputs but creep conditions/duration are absent
- **THEN** immediate results are scoped to that case and long-term verification remains NOT VERIFIED

#### Scenario: Range has no reviewed handling
- **WHEN** the source gives a range and the selected method has no accepted range/bound rule
- **THEN** the check remains NOT VERIFIED rather than calculating from its midpoint

### Requirement: Hardware anchorage and tipping require their own load paths
Hardware/joint checks SHALL require matching model/revision, installation geometry and a reviewed load distribution. Ratings SHALL NOT be multiplied across supports without documented sharing. Anchorage SHALL require identified substrate, matching anchor evidence, edge/spacing/embedment geometry and tension/shear/load transfer; cabinet-hanger ratings SHALL NOT establish wall capacity. Tipping SHALL use known footprint/mass/centre of gravity and applicable TV/misuse load cases. Countertop instruction checks SHALL match material/product/thickness/cutout/overhang/support conditions. Murphy-bed final safety claims SHALL remain gated by matching manual, full anchorage assessment and qualified review.

#### Scenario: Three bracket ratings without distribution
- **WHEN** three brackets have individual ratings but load sharing is undocumented
- **THEN** the system does not report three times the rating as verified shelf capacity

#### Scenario: Substrate unknown
- **WHEN** an anchor model is known but the actual wall substrate is not assessed
- **THEN** anchorage is NOT VERIFIED and the missing substrate is named

#### Scenario: Child climbing unresolved
- **WHEN** an entertainment unit passes a declared static load case but no applicable child-climbing case was assessed
- **THEN** the report lists tipping/misuse verification as incomplete

### Requirement: Reports distinguish a check result from whole-piece safety
Reports SHALL use `PASS_FOR_STATED_CASE`, `FAIL_FOR_STATED_CASE` or `NOT_VERIFIED` per method/load case, with results/units, limits when applicable, assumptions, sources/pages and unresolved checks. A numerical intermediate without a reviewed acceptance criterion SHALL NOT become a passing result. Any required unresolved hazard/load-path check SHALL keep the overall assessment incomplete. No result SHALL assert whole-piece safe-to-build status, DIN conformity or tested/certified approval. A visual/design/render approval SHALL NOT set an engineering status.

#### Scenario: Bending passes and anchorage unresolved
- **WHEN** a shelf passes its stated bending case but wall fixing is unverified
- **THEN** the report shows the bending pass, identifies unverified anchorage and keeps overall assessment incomplete

#### Scenario: Result has no criterion
- **WHEN** deflection can be computed but no applicable reviewed serviceability criterion exists
- **THEN** deflection is displayed with units while acceptance stays NOT VERIFIED

### Requirement: Calculation outputs are deterministic and immutable
A stored report SHALL retain the spec/input hash, complete input snapshot with original/canonical units, source/property revisions, method version, criteria, assumptions, results and missing inputs. Identical validated inputs and method versions SHALL yield identical numerical results. Later changes SHALL create a new report and mark prior assessments stale for current use rather than rewriting them. Subsequent retrieval/export of old evidence SHALL still pass current rights decisions.

#### Scenario: Same inputs twice
- **WHEN** a reviewed method runs twice on the same input snapshot
- **THEN** the numerical results and qualification fields are identical

#### Scenario: Source capacity changed
- **WHEN** an updated property revision changes the hardware capacity
- **THEN** the old report retains its original inputs/result and is marked stale for current advice
