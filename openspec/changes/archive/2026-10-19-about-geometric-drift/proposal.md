## Why

The owner asked on 2026-10-19 for an About page section on avoiding geometric drift. Tests in October 2026 showed that image AIs given a picture of a room do not keep the furniture's shape. They extended rooms and added doors to open cubbies, which is why `room-3d-pack` was deleted. Little Homey avoids this because every picture is drawn from the measured 3D model. The About page does not say so yet.

## What Changes

- The About page gains a section, after "Take your furniture anywhere", explaining in plain words that Little Homey's pictures keep your measurements. Proposed wording (approved by the owner 2026-10-19):

  > **Your measurements stay put**
  >
  > Many AI picture tools redraw a room each time you ask for a change. Along the way, things quietly drift: a shelf gets shorter, a wall moves, an open cubby suddenly has a door. Little Homey never redraws your furniture from a picture. Every piece is built from its exact measurements, and every picture shows that same model. A change happens only when you ask for it, and you see it in the new version. So what you see is what you can build.

- No technical terms, as the About requirement already demands.

Ladder step: none. Agents touched: none. Render guard and `bpy` allow-list: not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: the About page explains a fourth point, that pictures keep the piece's measurements (no geometric drift).

## Impact

- `frontend/src/routes/About.tsx` and its test.
