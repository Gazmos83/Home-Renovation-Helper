# Engineering assessments and calculator release

The assessment/report infrastructure is implemented. **No numerical engineering method is released.** All eight registered families remain unavailable and return `NOT_VERIFIED` with null calculated results. This preserves the approved scope while the exact source packages, reference cases and qualified reviewer are supplied. No safety factor, allowable resistance, creep coefficient or serviceability limit is chosen from memory.

The RAG foundation must pass its acceptance checks before a developer can accept a calculation method. See [engineering knowledge operations](ENGINEERING_KNOWLEDGE.md). Browser acceptance is still pending because this session has no connected browser. The plugins ship disabled; neither implementation enables them for the owner.

## Contracts available now

- Strict, version-scoped assessment inputs bind exact stored geometry and derived part IDs to product/grade/property/manual revisions. Omitted installation, service, support and load facts remain null or explicitly unresolved.
- `record_assessment_inputs` previews the facts and requires the owner's explicit `yes`. Its separate snapshot records estimates, not verified facts. A model cannot submit a `confirmed` field. Changing dimensions still requires the existing geometry revision confirmation.
- Original units are retained. Mass-to-force conversion is explicit: 10 kg becomes 98.1 N using 9.81. Invalid/nonfinite values, dimensionally wrong units, unknown resistance, unreviewed ranges and mean/characteristic test values cannot become allowable resistance. Stiffness and density cannot satisfy resistance inputs.
- Geometry is read from the stored spec and existing deterministic derivation. No cut list or drilling rule changes. Folds, polygons, partial divider support and unsupported load paths remain unresolved.
- Immutable input snapshots and reports retain spec/input hashes, original/canonical units, property/source revisions, method definitions, assumptions and missing checks. Updated geometry, facts, property review, method review or rights state marks historical reports stale without rewriting them.
- A code comparison can produce `PASS_FOR_STATED_CASE` or `FAIL_FOR_STATED_CASE` only against an exact cited criterion from an implemented, accepted method definition. A value without that criterion stays `NOT_VERIFIED`. Passing one check does not remove other unresolved checks. Overall status is `INCOMPLETE` or `COMPLETE_FOR_STATED_CASES`; conformity remains `NOT_ESTABLISHED`.
- Designer and Researcher have application-scoped calculate/read tools. Model-authored arithmetic or status text cannot replace report results. Conversation context and compressed memory carry report IDs/status only; fetching restores complete conditions and current staleness.
- Reports and their source-derived property values pass current rights checks on every read/export. Local-only or revoked evidence is removed from the cloud request copy. Legacy free-text material/spec notes are omitted from remote report copies. Persisted history is unchanged.

## Method families awaiting source packages

| ID, version 1 | Reserved domain | Required release evidence |
|---|---|---|
| `shelf_immediate` | Rectangular prismatic shelf in a declared support/load case | Exact material/grade, section/span/orientation, elasticity, allowable resistance, cited bending/deflection equations and acceptance limits |
| `shelf_creep` | Exact material/service/duration domain of an accepted shelf case | Cited creep model, sustained-load share, moisture/service conditions and duration |
| `joint` | Exact reviewed joint or tested assembly | Fastener identity, geometry/edge distances, load direction, matching assembly and criterion |
| `hardware` | Exact manufacturer model/revision/installation | Rated orientation, count and documented distribution; individual ratings are not automatically multiplied |
| `anchor` | Exact approval/substrate and installation case | Embedment/edge/spacing, tension/shear interaction and complete load transfer; hanger ratings do not verify the wall |
| `tipping` | Declared footprint/mass/centre-of-gravity and load cases | TV/accessory masses and sourced foreseeable-use/misuse cases, including child climbing where applicable |
| `countertop` | Exact product instruction check | Product/thickness/manual revision and matching overhang, cutouts and supports; no general stone solver |
| `murphy` | Individual stated checks | Matching mechanism/manual revision, complete wall/anchor assessment and qualified crush/impact/deployment review; no whole-bed approval |

The registry contains required inputs, units and domain descriptions. Its equations, acceptance criteria and independent reference sets are intentionally absent until reviewed. The acceptance API refuses these incomplete methods even if a caller submits `accept`.

For the first shelf release, provide rights-approved, technically reviewed source/version/block IDs for each equation and acceptance criterion; the exact board/grade/thickness and applicable conditions; independently reproduced reference values and boundary/negative cases; and an identified reviewer with documented qualifications and an acceptance record for the precise domain. Repeat that process before each later family is enabled. Formula or criterion changes require a new method version and qualified review.

## Developer and owner interfaces

The developer-only knowledge page includes method definitions and pending/accept/disable controls. `GET /admin/engineering-methods` reports the current definition hash and review state; `POST /admin/engineering-methods/{id}/review` appends a decision identifying the exact version/hash, reviewer, qualification evidence and scope/reference evidence. Rights approval and visual approval cannot substitute for this review. Acceptance additionally requires foundation acceptance, an implementation, cited criteria and independent reference cases with currently eligible reviewed evidence.

Owner-authenticated read routes under `/packages/{package}/versions/{version}/engineering/` expose assessment status, report lists and exact report IDs. Wrong piece/version requests are refused. The single-owner application gets piece identity from its conversation/path, never a model-supplied owner or package ID.

Calculations never start Blender, modify spec JSON, set `approved_at`, certify conformity or authorise installation. Conversation deletion removes only the conversation association; reports remain with the piece. Normal package/version deletion uses the existing cascade and leaves the independent source registry intact.

**Open deletion conflict:** existing deletion commits database removal before best-effort final folder cleanup; cleanup errors are ignored. The approved calculator scenario requires related records to survive any folder-removal failure. Move/database failures already preserve records, but post-commit cleanup is weaker. Task 4.4 remains incomplete pending the owner's choice of recoverable deletion or an explicit proposal revision. This behaviour has not been silently waived.

## Verification and rollback

Automated checks cover unit/basis contracts, synthetic criterion boundaries, owner confirmation through the graph, immutable database records, deterministic unavailable reports, geometry exclusions, property/fact/geometry/method/rights staleness, owner route scope, late cloud-rights checks, memory conditions, developer gates and separate visual approval. Synthetic comparison tests validate infrastructure; they are not independent engineering references and cannot release any family. No render or real model call is needed for these checks.

Disable a method through a new `disable` decision or disable `engineering_calculators` globally. Retain snapshots, reports and append-only review history. Re-fetching then reports unavailable/stale status; rollback never converts unverified history into a pass. Do not downgrade the database to disable functionality, because a migration downgrade removes assessment history.

The original estimate for the complete calculator change was 20–40 person-days across all families, with exact documents and qualified review as external dependencies. The completed infrastructure reduces remaining work, but a defensible revised estimate needs the first concrete source/domain package. The shelf equation/reference/review package is the next implementation dependency.
