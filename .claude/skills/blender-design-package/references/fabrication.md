# Fabrication

## Authoritative parts

Record confirmed overall dimensions, actual stock thickness/material, construction method, joint allowances, intended gaps, grain, edge treatments, hardware and required tolerances. Track missing or assumed values. Blueprint scale requires a stated dimension; perspective images and nominal furniture sizes are insufficient for cutting.

Use stable part IDs and instance identities. Separate components by physical manufacture: a plywood panel stays one panel; a glued top follows its specified boards and joints. Do not insert decorative gaps or turn integral tenons into separately purchased parts.

Derive geometry and output rows from one parts calculation. Mirror/array instances may share geometry, but each physical piece must be counted exactly once. Aggregate only parts with matching dimensions, material, grain, banding and machining, retaining the instance mapping. Do not infer quantities from object names alone.

Set dimensions explicitly: a cube created with size=1 has unit edges, so scaling by half the requested dimensions produces half-sized parts. Apply scale before dimension-sensitive modifiers. Use local component axes for length/width/thickness; a rotated world bounding box is not a cut size. Preserve world transforms when parenting.

## Cut and machining data

Retain the existing CSV contract where applicable:
`id,name,qty,l,w,t,material,grain,banding,notes,module`; `l,w,t` are millimetres. Preserve `spec.layers` mapping for the studio. The demo schema is a starting point, not proof of a complete manufacturing specification.

Distinguish finished dimensions, cut blanks and purchased stock. Declare what CSV dimensions represent. Compute tenon/trim allowances and edge-band deductions according to the confirmed construction. Saw kerf and sheet margins belong in stock layout/yield calculations; they do not automatically enlarge every finished part.

Specify joints and operations by part, datum face/edge, position, depth, diameter/profile and fit allowance. Include mating-part references and hardware quantities. Irregular shapes and angled cuts need dimensioned profiles/angles and machining instructions; three bounding dimensions are insufficient. Preserve required details in the specification and associated drawings.

Visible joint geometry must agree with those operations. Hidden detail can use simpler geometry when the specification and machining information remain complete. Edge radii/chamfers follow the design and stock thickness; a universal 2–5 mm bevel can damage thin parts and mating faces.

## Release checks

Before calling a package ready for cutting, verify:

- Positive dimensions, valid counts, material/thickness assignments and explicit units.
- Model component dimensions match the authoritative specification within the declared tolerance; instances reconcile with cut-list quantities.
- Assembly sums, intended clearances, joint engagement, hardware fit and opening/swing clearances agree.
- Cut blanks, grain direction, edge banding, machining and tolerances are resolved; stock/yield calculations account for kerf when supplied.
- CSV/spec/drawings refer to the same revision and contain no unresolved fabrication-critical assumptions.

Keep unresolved packages labelled draft and identify the exact missing values. Never extract cut dimensions from beauty renders, distorted meshes or cosmetic displacement.

If preparing a store list or quote, follow the app's selected-store capabilities and operator limits: toom only, in-store cuts, unsupported work classified as custom cuts, unknown feasibility explicit. Supplier pricing comes from the maintained list and overrides.
