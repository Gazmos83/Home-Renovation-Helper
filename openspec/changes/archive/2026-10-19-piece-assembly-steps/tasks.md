## 1. Frontend

- [x] 1.1 Add `SpecAssemblyStep` and `assembly?: SpecAssemblyStep[]` on `PieceSpec` in `frontend/src/lib/api.ts`.
- [x] 1.2 Add an `AssemblyPanel` to `Version` in `frontend/src/routes/Pieces.tsx`, after Pricing. It is a `<details>` "Assembly" for a built version only and reads `api.pieceSpec` under `["spec", packageId, version]`. It holds the ordered steps (two-digit number, title, body), the "no assembly steps" line and the read error. Verify with `Pieces.test.tsx` tests for "Built version with steps", "Built version without steps" and "Version not built".
- [x] 1.3 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`.

- [x] 1.4 `pnpm add jspdf`. Add `frontend/src/lib/assemblyPdf.ts`, which writes the title and the steps, wraps them and breaks pages. Verify with `assemblyPdf.test.ts`: title text, step order, wrapping, a page break for a long sequence, and the saved name.
- [x] 1.5 Add "Download assembly (PDF)" to `AssemblyPanel`, only when it lists steps. It imports `jspdf` dynamically and shows a failure next to the button. Verify with `Pieces.test.tsx` for "Download the steps as a PDF" (no server request) and "No steps, no download".
- [x] 1.6 Run `pnpm lint`, `pnpm test` and `pnpm build` again, and check that `jspdf` is a separate chunk.

## 2. Browser check

- [x] 2.1 Recorded browser pass: open a built piece on the Pieces page, open Assembly, and confirm the steps end in "Install". Download the PDF, open it, and confirm the title and every step are there. Passed by the owner 2026-10-19.
