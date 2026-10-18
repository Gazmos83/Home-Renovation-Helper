---
description: "Cycles settings, lighting, and the pass bar for a hyper-real apartment still. Read before final renders."
connections: [materials, photo-match, mcp-connection]
---

# Photoreal render

## Preview vs final

| | Preview | Final |
|---|---|---|
| Engine | Cycles GPU, fall back to CPU if GPU init fails | Cycles GPU |
| Samples | 128 + OIDN | 512–1024 + OIDN |
| Resolution | 1280×720 | 1920×1080, or the photo aspect |
| View | AgX, Medium High Contrast | same |
| Output | PNG next to the blend | PNG, 16-bit if the user will grade |

Do not use EEVEE for the deliverable. EEVEE is allowed only as a framing check.

## Light

- One Poly Haven HDRI matched to the photo (overcast, late afternoon, night interior). Strength 0.3–1.0. Rotate until the window highlight lands like the photo.
- Area light or portal on every window that is the key source. Portal size equals the opening.
- Practicals only where the photo shows a lamp on. Color temperature from the photo: daylight 5200–6200 K, warm interior 2700–3200 K.
- No black environment, no single sun blasting an interior with no fill.

## Pass bar

Reject the still if any of these are true:

- Pure white walls (base color above 0.9) or pure black gaps
- Flat roughness with no variation on wood or paint
- Missing contact shadow under furniture
- Window glass that is opaque or a mirror
- Camera clipping the floor
- A room dimension that disagrees with the manifest

Save the `.blend` after the shell, after dressing, and after the final still. Report camera name, samples, and output path.
