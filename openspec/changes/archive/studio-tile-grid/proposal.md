## Why

The Design Studio tabs show one tall card per piece, room or model, each holding everything about it (versions, renders, pricing, compositions, 3D views, upload form). With more than a few items the owner scrolls a long page to find one. The owner asked (2026-10-14) for a second navigation column, a grid of picture tiles that fills one laptop or phone screen, and each item's detail in a popup. The model library shows no picture of a model at all.

## What Changes

- **Second column.** Choosing Pieces, Measured Rooms or Model Library on the left rail opens a sub-menu column beside it. Pieces → "All pieces"; Measured Rooms → "All rooms"; Model Library → "Uploaded models" and "Upload model". On a phone the sub-menu becomes a horizontal tab strip above the content, and the left rail stays as it is.
- **Tile grid on all three tabs.** Every piece, room (and standalone composition) and uploaded model is a tile (style A: picture on top, name and one line of size below, state badge in the corner). The grid is 4 across × 4 down on a laptop (≥ 1024 px wide) and 2 across × 3 down below that (Galaxy S25 reference, about 360 × 780 CSS px). Each grid fills the screen below the header.
- **Pages, not scroll.** More than 16 tiles (laptop) or 6 (phone) are split into pages with Previous / Next and "Page N of M". The page number is in the address (`?page=2`).
- **Addressable popup.** Choosing a tile opens the item's detail in a dialog with its own address (`/studio/pieces/<id>`, `/studio/rooms/<room>`, `/studio/rooms/compositions/<slug>`, `/studio/models/<model-id>`). The dialog holds what the item's card holds today, unchanged. Browser Back or Esc closes it, and a reload or link reopens it. On a phone the dialog fills the screen. A tile starts loading its detail on hover or focus.
- **Upload model in a window.** "Upload model" (`/studio/models/upload`) opens the existing upload form in a dialog over the Uploaded models grid. A successful upload closes it and the new model appears as a `checking` tile.
- **Model preview pictures.** When a model reads `ready` and has no picture, the browser draws it once with three.js (GLB, glTF or OBJ from the model's own served files) and uploads a small PNG. The backend gains an owner-gated thumbnail route that checks the PNG's bytes and size. A model without a picture shows a placeholder icon.
- **Unchanged.** "Create A New Piece" and the import-template link stay above the Pieces grid. The piece inspector keeps its address. Old addresses `/pieces`, `/rooms` and `/models` still open their tab.

No ladder step and no agent is touched: this is Studio UI plus one model-library route. The **render guard and the bpy allow-list are not affected**. The preview picture is a WebGL snapshot in the owner's browser, not a Blender render, and no Blender process runs for it.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `studio-ui`: the Design Studio gains a sub-menu column (top tabs on a phone), a paged tile grid per tab and an addressable detail dialog. The Pieces, Measured Rooms and Model Library requirements move their card content into that dialog, and the Model Library splits into "Uploaded models" (grid with pictures) and an "Upload model" dialog.
- `model-assets`: a model gains a preview picture, uploaded by the owner's browser and served by id.

## Impact

- **Frontend:** `routes/Studio.tsx` (sub-menu, nested routes), `routes/Pieces.tsx`, `routes/Rooms.tsx`, `routes/ModelLibrary.tsx` (card → tile + dialog body), `App.tsx` (nested `/studio/:tab/*` routes). New `components/ui/dialog.tsx` (shadcn), `components/studio/{TileGrid,Tile,SubMenu}.tsx`, `lib/modelThumbnail.ts` (offscreen three.js snapshot), and their tests.
- **Dependency:** `@radix-ui/react-dialog` (shadcn Dialog). three.js loaders (`GLTFLoader`, `OBJLoader`, `MTLLoader`) come from the existing `three` package.
- **Backend:** `app/api/models.py` gains `PUT` and `GET /models/{id}/thumbnail`. `ModelOut` gains `entry` and `has_thumbnail`. `app/assets/models.py` stores the picture under `<upload_root>/model-thumbnails/<id>.png` and deletes it with the model. No migration and no agent, generator or render change.
- **Specs:** `openspec/specs/studio-ui/spec.md`, `openspec/specs/model-assets/spec.md`.
