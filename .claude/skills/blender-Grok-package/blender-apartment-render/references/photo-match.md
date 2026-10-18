---
description: "Match Blender cameras to apartment photos and judge the difference. Read before claiming a view is photoreal."
connections: [measurement-intake, photoreal, mcp-connection]
---

# Photo match

A hyper-real render that does not match the user's photograph is a failure, even if the materials look good.

## Camera

- Eye height default 1.50 m. Match the photo if the horizon is visible: horizon line in frame equals camera height.
- Start at the manifest lens. Phone photos are usually 24–28 mm equivalent. Do not use 50 mm unless the photo is clearly compressed.
- Aim with look-at, then nudge yaw by at most 5 degrees after a screenshot compare.
- Load the photo as a camera background image at 50% opacity for alignment. Hide it before the final render.
- Sensor fit horizontal. Clip end 100 m.

## Compare loop

1. Render a 128-sample preview from `cam_<photo>`.
2. Put the preview beside the source photo. Check, in order: horizon, window position, door swing side, floor line, major furniture silhouette.
3. Fix the largest error only, then re-render. Three loops maximum per camera before asking the user which mismatch to prefer.
4. Do not add furniture that is not in the photo or on the user's list just to fill the frame.

## Hero props

Use Poly Haven or a local asset for sofas, tables, and plants. Use image-to-3D only for a distinctive piece in the photo (a specific lamp, a built-in cabinet). Scale the import to a measured dimension, set the origin on the floor, and join it to collection `Furniture`.
