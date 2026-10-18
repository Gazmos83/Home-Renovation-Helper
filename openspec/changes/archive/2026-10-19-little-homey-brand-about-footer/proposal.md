## Why

The end-to-end review of 2026-10-15 asks for three things:
- an About page that explains the app to someone who is not technical;
- a footer;
- a README that opens with the app's concept in plain words.

On 2026-10-18 the owner named the app **Little Homey**, "your home renovation assistant". Today the app has no name of its own: the header says "Home Renovation", the browser tab says "Home Renovation Agents", and there is no icon (`frontend/public` does not exist).

## What Changes

- **Rename to Little Homey everywhere the owner sees a name:**
  - the header brand link (`frontend/src/App.tsx`);
  - the browser tab title (`frontend/index.html`);
  - the API's OpenAPI title (`backend/app/main.py`);
  - the README title.
- **An icon.** A simple SVG house drawn for this change, used as the favicon and beside the name in the header. It uses `currentColor` for the header so it follows the light and dark themes.
- **An About page at `/about`** for a signed-in owner, linked from the header (beside Help) and from the footer. It is plain words for a non-technical reader, covering the owner's three points:
  - 3D renders on a low-powered machine;
  - the AI-guided furniture revision is where the magic is;
  - revised furniture can be exported into an existing house render or added to a room in the app.
  
  The draft text is in design.md for the owner to review before apply.
- **A footer on every page**, the sign-in page included: "© 2026 Little Homey" and the app's version and build, e.g. "v0.1.0 · f08d9cb". The version comes from `frontend/package.json`, and the build is the short git commit read when Vite starts or builds. It is one muted line, frozen at the bottom of the screen (owner, 2026-10-19), with the page and its panes ending above it so it covers no content.
- **README opens with a concept section** in plain words, a separate and longer text than the About page:
  - name and icon;
  - a table of contents;
  - "Concept", with three journeys: create your furniture piece; create your room or home; create a realistic render.
  
  The owner's draft is fine-tuned in design.md. The technical sections stay below it, unchanged.
- **Unchanged:**
  - the repository, Python package and npm package names (`home-renovation-agents-studio`);
  - CLAUDE.md;
  - routes other than the new `/about`;
  - the help center's topics (none names the app).

Ladder: none (no schema or generator change). Agents touched: none. The **render guard** and the **bpy allow-list** are **not affected**. The homeowner view still shows no model, prompt, token or cost: the footer's build id is a commit hash, not a model.

Estimate: about 90 minutes:
- rename and icon, about 20 minutes;
- About page, about 25 minutes;
- footer with version and build, about 20 minutes;
- README concept, about 25 minutes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`:
  - the header's name changes in the requirement "The Workspace is the home page";
  - added: the app name and icon, the About page, and the footer.

## Impact

- `frontend/index.html` (title, favicon link); new `frontend/public/favicon.svg`; a `HouseIcon` component (inline SVG) under `frontend/src/components/`.
- `frontend/src/App.tsx`: brand, `links` gains About, the `/about` route, and the footer rendered after `<Routes>`. New `frontend/src/routes/About.tsx`. New `frontend/src/components/Footer.tsx`.
- `frontend/vite.config.ts`: `define` for `__APP_VERSION__` and `__APP_BUILD__`; `src/vite-env.d.ts` declares them. Vitest gets the same defines.
- `frontend/src/App.test.tsx`: the header link expectations change from "Home Renovation" to "Little Homey" and gain "About". New `About.test.tsx` and `Footer.test.tsx`.
- `backend/app/main.py`: the FastAPI `title`. `README.md`: new top section, title.
- No backend behaviour, migration or API change. `/about` is a page only, so no proxy entry is needed.
