---
description: "Wall, slab, door, and window construction details. Read when the generated shell is wrong or booleans fail."
connections: [measurement-intake, mcp-connection, photoreal]
---

# Shell and openings

`scripts/generate_shell.py` writes five chunks: scene, rooms, openings, cameras, render setup. Send them in order through [[mcp-connection]].

## Geometry rules

- `polygon_mode: interior` means the polygon is the inside face. Exterior walls are offset outward by half the thickness. Shared edges are built once, centered on the line.
- Floor and ceiling chunks use the room bounding rectangle. If a room is L-shaped, replace that plane with a filled polygon mesh before rendering. Do not leave the bounding box visible.
- Wall origins stay at the segment midpoint so a boolean cutter can find them by XY distance.
- Openings are cutter cubes, three times wall thickness, boolean DIFFERENCE, FLOAT solver. Window glass is a separate 1 cm slab. Doors are a 4 cm slab, closed, until the user asks for an open door.

## When the shell is wrong

| Symptom | Fix |
|---|---|
| Walls land inside the room | Polygon was centerline but mode is interior. Switch mode or flip the offset. |
| Missing party wall | Edge keys did not match because of millimetre drift. Snap both rooms to 1 mm. |
| Boolean deletes the wall | Cutter missed the wall. Snap cutter XY to the wall location, then apply. |
| Non-manifold black faces | Recalculate normals outside. Do not render until the viewport is clean. |
| Z-fighting floor | Drop the floor by slab/2 and keep the wall bottom at z=0. |

Apply bevel of 2 mm only after booleans are applied. A bevel modifier on an unapplied boolean breaks the cut.

Name everything `floor_<room>`, `wall_<room>_<i>`, `cut_<opening>`, `cam_<photo>`. Later photo match depends on those names.
