## 1. Method and assessment contracts

- [x] 1.1 Add a closed method/version registry with units, domain, citations, criteria, reference cases and qualified-review state; verify unreviewed methods remain unavailable and arbitrary model expressions cannot execute.
- [x] 1.2 Add finite-value/unit/basis/range validation, including explicit kg-to-N conversion; verify invalid units, unreviewed bounds, unknown properties and mean/test values cannot become allowable resistance.
- [x] 1.3 Add version-scoped assessment schemas for exact material/hardware/property bindings, loads, supports and environment/installation facts; verify omitted facts remain unresolved instead of receiving defaults that imply verification.
- [x] 1.4 Add an owner-confirmed assessment-input action separate from geometry revision; verify model-proposed facts cannot be stored as confirmed and existing dimension-change confirmation remains mandatory.
- [x] 1.5 Bind supported geometry to the exact stored spec/derivation and declared load paths; verify partial dividers, folds and polygonal sections outside a reviewed domain return NOT VERIFIED without altering cut lists.

## 2. Shelf methods first

- [x] 2.1 Record source-backed equations, acceptance criteria and independent reference cases for supported rectangular shelf support/load cases; verify a qualified reviewer has accepted the precise domain before enabling any method.
- [ ] 2.2 Implement bounded immediate bending/deflection functions and case validation; verify independent reference results, limiting cases, load distribution and unsupported-domain failures.
  - 2026-10-18: immediate deflection done (`shelf_immediate` v1, Hyman 1995, L/400, simply supported, uniform load). Bending strength is outside v1 by the owner's choice; it needs a cited strength source and a new method version before this task is ticked.
- [ ] 2.3 Record and implement a cited creep model only for its material/duration/service domain; verify sustained-load share and moisture/duration conditions are required and missing long-term evidence keeps that check unverified.

## 3. Connections and installation methods

- [ ] 3.1 Define and review a bounded joint method or exact tested-assembly contract; verify fastener identity, edge distances, load direction and source criteria are explicit before release.
- [ ] 3.2 Implement joint checks for that accepted domain; verify known reference cases and rejection of generic confirmat ratings, missing geometry and dissimilar assemblies.
- [ ] 3.3 Implement exact hardware capacity/instruction checks with reviewed distribution rules; verify wrong revision/orientation and unsupported multiplication of ratings cannot produce a pass.
- [ ] 3.4 Define and review anchor/load-transfer cases tied to exact approval, substrate and installation geometry; verify hanger-only evidence and unknown wall substrates do not satisfy the contract.
- [ ] 3.5 Implement the reviewed anchorage cases; verify tension/shear interaction, edge/spacing/embedment constraints and independent source-backed cases before enabling them.
- [ ] 3.6 Define and review bounded tipping/load cases and implement footprint/mass/centre-of-gravity checks; verify TV/accessory and applicable child-climbing cases are explicit and unresolved use scenarios keep the assessment incomplete.
- [ ] 3.7 Add exact-product countertop instruction checks and Murphy-bed individual-check gates; verify unsupported countertop geometry and missing mechanism manual/wall/anchor/reviewer information cannot imply whole-piece approval.

## 4. Reports and persistence

- [x] 4.1 Add immutable input snapshots/report persistence with spec/input hashes, source/property/method revisions and original/SI units; verify identical inputs yield identical numerical values and old reports are never rewritten.
- [x] 4.2 Implement PASS_FOR_STATED_CASE, FAIL_FOR_STATED_CASE and NOT_VERIFIED results with scoped criteria, missing inputs and overall incompleteness; verify an intermediate value without criteria cannot pass and one passing check cannot mark the piece safe.
- [x] 4.3 Add current-status/staleness checks for geometry, facts, properties, methods and source rights; verify changed/revoked inputs mark the current view stale and historical excerpts still pass the foundation remote-use gate.
- [x] 4.4 Add owner-scoped report routes and transactional package/version deletion handling; verify cross-piece access is denied, deletion failures retain all related records and conversation deletion only removes the conversation association.

## 5. Tools, memory and developer controls

- [x] 5.1 Expose calculation/report tools to Designer and Researcher, scoped by application context; verify replies use code-generated values and an unavailable tool never reuses remembered arithmetic as a new calculation.
- [x] 5.2 Add active-piece report IDs/status to house-file context and fetch complete reports on demand; verify other pieces' reports are absent and summary compression cannot drop conditions or promote a stale report.
- [x] 5.3 Add developer method-review/enable/disable controls and preserve separate visual approval; verify no calculation sets piece approval, starts Blender or authorises installation and rollback only disables methods while retaining history.

## 6. Independent validation and release

- [ ] 6.1 Assemble source-backed reference and negative cases across enabled families, reviewed independently of implementation; verify coverage of units/ranges, exact model matches, unsupported geometry, missing criteria, revocation and boundary/load cases.
- [ ] 6.2 Run pure-function/reference tests and API/report/privacy/deletion tests serially against the designated test database; verify repeatability and all review gates without Blender or renders.
- [x] 6.3 Run ordinary design/revision/cut-list/pricing/approval regressions with mocked external boundaries and required backend checks; run frontend checks for any changed controls, verify they pass and record attributable failures/resolutions.
- [x] 6.4 Document each enabled method's accepted domain, qualified review, references, limitations and disable-method rollback; verify methods lacking exact source evidence or reviewer acceptance remain disabled and reports never claim conformity/certification.
