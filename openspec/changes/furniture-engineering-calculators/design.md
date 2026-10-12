## Context

See `proposal.md`. The foundation supplies versioned, rights-approved evidence, exact numerical records and a safety envelope. Existing `guidelines/checks.py` is a closed set of geometric guideline checks; `derive.py` calculates parts, drilling and bracket layouts, not structural resistance. Material slots currently have names/thickness but no verified engineering identity. A cut width or a fixed divider attachment does not define a load path.

## Goals / Non-Goals

**Goals:** Reproducible, reviewed results for bounded furniture cases, with explicit incomplete/unsupported outcomes and immutable input provenance.

**Non-Goals:** Whole-piece safe-to-build approval, compliance certification, arbitrary finite-element analysis, dynamic Murphy-bed mechanism modelling, deriving anchor capacity from hanger ratings or treating mean laboratory strength as allowable resistance.

## Decisions

### 1. A closed registry with per-method release gates

Add a pure-Python calculation service under `backend/app/engineering/`, with a closed method ID/version, required units/input schema, applicability conditions, method citation, reviewed acceptance criteria and reference-case set. Methods are unavailable until a qualified review record accepts their scope and references; unreviewed methods return `NOT VERIFIED` with a reason. Formula/parameter changes create a new version, not an in-place report rewrite. No model-generated expression, Python or SQL is evaluated.

Implement these bounded families in order:

| Family | Initial domain and mandatory evidence |
|---|---|
| Bending and immediate deflection | Rectangular prismatic shelves; declared simple support/cantilever and supported load distribution; verified product/grade, section, span, orientation, E and applicable resistance/limit criteria |
| Long-term deflection/creep | The above cases only, with cited product/material creep model, load duration, service/moisture conditions and sustained-load share |
| Joint resistance | A declared joint type/fastener/edge-distance geometry and load direction covered by a reviewed method or exact tested assembly; no generic confirmat capacity |
| Hardware capacity | Matching manufacturer model/revision, installation orientation, hardware count and supported load distribution; do not multiply ratings unless documented sharing permits it |
| Anchorage | Matching anchor approval/manual, identified substrate, edge/spacing/embedment/installation geometry and tension/shear/load transfer under a reviewed method; unknown/dissimilar substrates remain unverified |
| Tipping | Declared support footprint, mass/centre of gravity, TV/accessory loads and explicitly sourced foreseeable-use load cases, including child climbing when applicable; unknown scenarios remain incomplete |

Countertop checks use exact product/overhang/cutout/support instructions; they are conditional capacity/instruction checks, not a general stone solver. Murphy-bed-related methods can report individual checks only. Verified matching manual, full wall/anchor assessment and qualified review remain necessary, and still do not constitute product certification.

The numerical formulas, safety factors and serviceability thresholds are not chosen from memory in this proposal. Before enabling a method, review a cited equation/criterion applicable to its domain and independently reproduce its reference cases. Different unsupported cases return `NOT VERIFIED`; adding a new domain requires a spec-reviewed method change. This release gate preserves the selected scope without guessing unavailable product parameters.

### 2. An assessment is separate from the furniture spec

Use a version-scoped assessment schema with piece/version ID, part IDs, exact material/product/property revision bindings, hardware/source revision IDs, loads, support/boundary geometry, environment/duration and installation facts. Geometry is read from the stored spec and its deterministic derivation. The model may propose bindings/facts, but code requires explicit owner confirmation before storing them. Retain the original unit alongside the canonical SI value, and convert mass to force explicitly. Treat user estimates as assumptions, not verified facts.

Keep assessment facts in separate tables rather than adding loosely defined fields to strict Blender JSON. This avoids changing generators and material pricing keys. Confirmation uses the current preview/yes mechanism through a dedicated assessment-input action. Changes to piece dimensions still follow `revise_package` and its requested-measurement checks.

A divider splits a structural span only if its actual support path is inside the method's reviewed domain. Folded or polygonal shelves must not be reduced to their widest/narrowest cut width unless a reviewed method covers that reduction. Such parts return unsupported-domain status in the first methods.

### 3. Deterministic values with complete validation

Pure functions validate finite values, signs, dimensions and ranges before computation. Missing inputs, unverified property basis, model mismatch, stale/revoked evidence or unsupported geometry produce `NOT VERIFIED`, with null calculated resistance where a calculation cannot run. A physically computed intermediate value can be reported with units even when no applicable acceptance criterion exists, but it cannot produce a passing check.

Do not narrow source ranges to their midpoint. Use a reviewed conservative bound/range propagation only when the method defines it; otherwise return an unresolved input. Keep mass, force, pressure/modulus and distributed-load units distinct. A hardness/appearance value cannot satisfy an elasticity or strength field.

Use statuses `PASS_FOR_STATED_CASE`, `FAIL_FOR_STATED_CASE`, `NOT_VERIFIED`. Overall assessment status is incomplete if any required hazard/load-path check is unverified, even if shelf bending passes. The foundation answer renderer retains its preliminary/conformity distinction; no whole-design `SAFE` status is introduced.

### 4. Immutable reports and current-status checks

Persist assessment-input snapshots and immutable calculation reports with spec hash, inputs/original units, property/source revisions, method version, reference criteria, load cases, assumptions, intermediate/result values, limit/utilisation when meaningful, missing inputs and review requirements. Repeated identical inputs/method versions have identical numerical results; timestamps and report IDs can differ.

Changing a spec creates a new geometry version and does not mutate an old report. Changing assessment facts or material bindings creates a new snapshot. A current view marks old reports stale when any input/property/method or evidence-rights state changes. Store original reports locally for audit under retention rights; subsequent cloud use must pass the foundation rights gate for source-derived properties and report evidence as well as quoted passages. Do not quote a revoked excerpt or expose a local-only property simply because it appears in a report.

Expose owner-gated read routes and a read/calculation plugin for Designer and Researcher. Piece identity comes from conversation/path scope. The report does not set the existing `approved_at`, start Blender or authorise installation. Package/version deletion removes associated assessment/report records through the existing deletion transaction; it does not remove source registry records needed by other pieces. Conversation deletion retains piece reports and removes the conversation association.

### 5. Memory and answers use report IDs, not remembered arithmetic

The house file gives only the conversation's active piece's relevant report status/ID and staleness; full reports are fetched on demand. Sources, numeric results and unverified flags are supplied as complete typed evidence to the answer renderer; narrative summaries cannot replace them. When a tool is off or unavailable, report calculation unavailable rather than reproducing a previous answer as a new result.

The visual Reviewer remains a discrepancy tool. An engineering question about a view (for example load capacity of the top shelf) routes to the evidence/calculation specialist, not to visual judgement. Ordinary dimension edits do not trigger all engineering checks automatically, but any prior assessment shown for changed geometry is marked stale.

## Risks / Trade-offs

- [Right formula used outside its domain] → Mandatory applicability validation and negative tests for folds, partial supports, mixed geometry and load direction.
- [Reference values lack a design basis] → Distinguish mean/characteristic/allowable records and require cited acceptance criteria and method review.
- [Ratings multiplied despite unequal loads] → Require a stated reviewed distribution; missing distribution means `NOT VERIFIED`.
- [Passing one check mistaken for safety] → Scope statuses per case, list remaining checks and preserve qualified-review gates in renderer and reports.
- [Source/model updates make reports stale] → Immutable versions, input hashes and current-status checks without rewriting history.

## Migration Plan

1. Apply after foundation acceptance. Add assessment/report persistence and method registry disabled by default; preserve spec and drilling derivations.
2. Implement and independently review shelf cases first, then the remaining bounded families. Source/method review records are dependencies for enabling each family, not assumptions made by the model.
3. Validate source-backed reference examples, independent analytical comparisons, limiting cases and deliberately invalid inputs. Run ordinary design/cut-list/approval regressions with mocked Blender, requiring no render.
4. Enable each accepted method through developer controls. Roll back by disabling calculation methods/plugin; retain report history. No rollback may relabel unverified reports as passing.

## Effort and release dependencies

One developer familiar with the codebase, 8-hour person-days, **20–40 additional days** after the foundation:

| Work | Days |
|---|---:|
| Input/report contracts, unit/basis validation and method-review plumbing | 3–5 |
| Bounded bending, deflection and creep methods | 5–9 |
| Joint and exact hardware checks | 4–8 |
| Anchorage and tipping cases; countertop instruction checks | 4–9 |
| Persistence, tools/answers, reference tests and regressions | 4–9 |
| Total | **20–40** |

Confidence is low-to-medium because exact product/anchor documents and their supported cases are not supplied yet. Qualified engineering review, documented rights and manufacturer data are external lead time. Reviewers must approve the cited methods, acceptance limits and reference results before a method is enabled; this estimate is not an engineering certification or a promise to verify every possible piece.

## Open Questions

`TODO(user)` operational inputs: nominate the qualified reviewer and provide the first actual board, hardware/anchor model and installation/load facts. Their absence keeps affected methods/assessments unverified; the schema, integration approach and task breakdown remain as proposed.
