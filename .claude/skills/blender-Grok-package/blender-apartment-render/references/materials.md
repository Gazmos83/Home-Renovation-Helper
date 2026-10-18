---
description: "Principled BSDF starting values for apartment surfaces. Read when assigning or correcting materials."
connections: [photoreal, shell-and-openings, photo-match]
---

# Materials

Assign these as a first pass, then tint from the photo. Values are Principled BSDF: base color RGB, roughness, transmission weight.

| Id | Use | Base | Roughness | Notes |
|---|---|---|---|---|
| warm_white_paint | walls | 0.78 0.75 0.70 | 0.55 | Never 1,1,1 |
| matte_white | ceiling | 0.82 0.82 0.80 | 0.70 | Slightly darker than walls |
| oak_floor | timber floor | 0.45 0.28 0.14 | 0.45 | Add a stretched noise bump, scale 4 |
| door_wood | doors | 0.25 0.14 0.07 | 0.40 | |
| glass | windows | 0.85 0.90 0.92 | 0.05 | Transmission 1, IOR 1.45 |
| brushed_metal | frames | 0.55 0.55 0.53 | 0.35 | Metallic 1 |
| fabric_sofa | upholstery | from photo | 0.75 | Sheen low, no transmission |
| ceramic_tile | bath | 0.75 0.75 0.73 | 0.25 | Clearcoat 0.2 only if glossy in photo |

Poly Haven texture sets replace these colors when a close match exists. Keep the roughness in the table if the downloaded map is too shiny. Add a 2 mm bevel on furniture and wall corners after booleans are applied so edges catch light.
