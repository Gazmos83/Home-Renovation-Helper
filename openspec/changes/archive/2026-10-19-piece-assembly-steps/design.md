## Context

`derive.py:_assembly` writes `assembly: [{step, title, body}]` into each built version's `spec.json`. The inspector already reads that document with `api.pieceSpec` under the query key `["spec", packageId, version]`. The Pieces dialog shows one version at a time through `Version`: actions, downloads and the Pricing `<details>`.

## Decisions

- **Placement: a collapsed `<details>` in `Version`, after Pricing.** It follows the existing Pricing pattern, keeps the dialog short and needs no new component library. The alternative, an inspector tab, is a different page and is not what was asked for.
- **Reuse `api.pieceSpec` and the `["spec", …]` query key.** The inspector and the Pieces page then share one cached read. The query is enabled only when the version's status is `succeeded`, because only a built version has a `spec.json`.
- **Port the old panel's markup, minus the Stock footer and the intro sentence about the generator.** The footer depends on `spec.parameters`, which is absent. The intro sentence talks about the generator, which the homeowner view avoids.
- **Wording "Assembly".** The old tab's name. Its last step is the installation.

- **PDF made in the browser with `jspdf`** (owner's choice, 2026-10-19, over a file written at build time). It works for every built version, including those built before this change, and touches no backend. `jspdf` is imported dynamically on the button press so it stays out of the main bundle. The layout is A4 portrait in the built-in Helvetica: a title, then each step as "NN Title" with its body wrapped below, and a new page when the next line would cross the bottom margin. The page building lives in `lib/assemblyPdf.ts`, apart from the component, so it can be unit-tested against a fake document.
- **Not added to the version file list or the ZIP bundle.** Both list files on the server, and this PDF is never stored there.

## Risks

- The built-in PDF fonts cover Latin-1 (WinAnsi). The generated steps and German umlauts are covered. A workshop note with characters outside Latin-1 (for example `→`) would print wrongly. Embedding a font would fix that, at about 300 kB; it is left out until it is needed.

- Older versions built before `assembly` was emitted show the "no assembly steps" line. That is accurate, not an error.
