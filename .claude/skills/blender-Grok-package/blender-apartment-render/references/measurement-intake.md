---
description: "Extract a metric apartment manifest from blueprints and photos. Read before modeling."
connections: [shell-and-openings, photo-match, materials]
---

# Measurement intake

Never scale a room by eye. Build `apartment-manifest.json` from the plan, validate it, then generate Blender code.

Template: `assets/apartment-manifest.example.json`.

```bash
python3 scripts/validate_manifest.py apartment-manifest.json
python3 scripts/generate_shell.py apartment-manifest.json --out /tmp/apartment-chunks
```

## What to pull from a blueprint

- Units. If the plan is millimetres or feet, convert to metres in the manifest.
- Interior face polygons, counter-clockwise, origin at a labeled corner. +X east, +Y north, +Z up.
- Wall thickness. Use 0.12 m for a typical interior partition if the plan does not dimension it. Do not invent structural thickness for exterior walls; mark it unknown and use the drawn thickness.
- Ceiling height. Default 2.50 m only after saying so. Doors are 2.05 m unless noted.
- Openings: kind, room, from/to on the wall line, width, sill, height.
- North arrow and which facade the sun hits in the photos.

## What to pull from photos

- One row per photo: file, room, estimated lens (phone wide ≈ 24 mm full-frame equivalent), camera location, look-at point, time-of-day note.
- Material evidence: floor species, wall color (never pure white), metal vs paint on frames, curtain color.
- Do not copy clutter that the user wants removed. Ask once, then keep a `furnish` list separate from the shell.

## Scale checks

| Check | Pass |
|---|---|
| Door width | 0.70–1.00 m |
| Window sill | 0.70–1.10 m for living rooms, lower only if the photo shows it |
| Ceiling | 2.30–3.20 m in ordinary apartments |
| Room area | matches the plan label within 5% |

If a photo and the plan disagree, trust the dimensioned plan for size and the photo for materials, camera height, and light.
