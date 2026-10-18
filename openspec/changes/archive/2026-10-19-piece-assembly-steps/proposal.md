## Why

The predecessor's studio had an Assembly tab (`frontend/src/components/studio/AssemblyPanel.tsx`) that showed a package's numbered shop sequence, ending with the installation step. The port kept the derivation: every built version's `spec.json` still carries `assembly` from `derive.py:_assembly`. But no page shows it, so the owner cannot read how a piece is assembled and installed without opening the JSON. The owner asked on 2026-10-19 for these instructions to come back on the Pieces page.

## What Changes

- **Assembly on the Pieces page.** A built version in the piece dialog gets an "Assembly" dropdown, next to Pricing. It reads the version's `spec.json` and lists its `assembly` steps in order: a two-digit step number, the title and the body. The final step is the installation step ("Install: Position, level and fix the build in place.").
- A built version whose `spec.json` has no steps says "This version lists no assembly steps." A version that is not built offers no dropdown. A failed read shows its reason in the dropdown.
- The steps are shown as written. Nothing is derived, edited or saved in the browser.
- **Download as PDF** (asked 2026-10-19). When the dropdown lists steps, it offers "Download assembly (PDF)". The PDF is made in the browser from the steps shown. It is titled with the piece and version and holds every step's number, title and body. It is saved as `<piece>-v<N>-assembly.pdf`. Nothing is stored on the server, and the ZIP bundle is unchanged.
- **Not ported:** the old panel's "Stock" footer read `spec.parameters`, which a custom-build `spec.json` does not carry. The predecessor's `shopTab` gating and studio tabs are not ported either.

Frontend only. No backend, schema, generator, agent or render change, so the render guard, the allow-list and the ladder are not affected. `PieceSpec` in `frontend/src/lib/api.ts` gains the optional `assembly` field. The frontend gains one dependency, `jspdf`, loaded only when a download is asked for.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: the Pieces page shows a built version's assembly steps.

## Impact

- `frontend/src/lib/api.ts`: `SpecAssemblyStep`; `assembly?` on `PieceSpec`.
- `frontend/src/routes/Pieces.tsx`: an `AssemblyPanel` in `Version`, with the PDF download.
- `frontend/src/lib/assemblyPdf.ts`: builds the PDF from the steps.
- `frontend/package.json`, `pnpm-lock.yaml`: `jspdf`.
- `frontend/src/routes/Pieces.test.tsx`, `frontend/src/lib/assemblyPdf.test.ts`: tests for the scenarios.
