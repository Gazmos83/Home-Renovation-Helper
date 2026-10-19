## Why

The owner wants a marketing page: what a visitor sees before signing in (2026-10-19). Today a signed-out visit to any address, `/` included, goes straight to the bare sign-in form. A mock-up exists in `docs/Little Homey Landing page/` (a Grok-built TanStack Start workspace). It is reference only and gitignored by this change's request.

The brand change kept "a marketing site" as a non-goal (little-homey-brand-about-footer, 2026-10-18). The owner now asks for one, so this change lifts that non-goal for the signed-out `/` page only.

## What Changes

- **A marketing page at `/` for a signed-out visitor.** It is built from the mock-up's layout, in the app's existing theme and fonts (owner, 2026-10-19):
  - a top bar with the house icon and "Little Homey" at the left, and "Meet the crew", "About" and "Sign in" links at the right;
  - a hero section: a short line above the headline, the headline "Hello from Little Homey and his crew", one paragraph, a "Sign in" button to `/login`, and the mascot image beside it (stacked below on a phone);
  - a closing card: "We help you make your house a home." with "Little Homey" under it;
  - the existing frozen footer.
- **A crew page at `/crew` for a signed-out visitor** (owner, 2026-10-19), opened from "Meet the crew" in the top bar beside "Sign in". It shows the same top bar, "Meet the crew", the crew's names and jobs, and the footer. A signed-in owner opening `/crew` sees the same page under the owner's header.
- **The crew leaves the About page** (owner, 2026-10-19). Its "Meet the crew" section (added by `meet-the-crew`) moves to the crew page. **Behaviour change** for the signed-in owner.

  The draft texts are in design.md for the owner to review.
- **The mascot image** `homey.jpg` (1045 × 1568, 204 KB) is copied from the mock-up into `frontend/public/` and committed. Nothing else from the mock-up is copied: no TanStack Start, no Grok scripts, no new packages, no Google Fonts.
- **Routing.**
  - `/` signed out shows the marketing page.
  - `/` signed in still opens the Workspace.
  - Every other signed-out address keeps its behaviour: protected pages and unknown addresses still show the sign-in page, so a deep link still returns there after sign-in.
  - Sign-out still shows the sign-in page.
- **About opens to visitors** (owner, 2026-10-19). "About" in the top bar, beside "Meet the crew", opens `/about` for a signed-out visitor under the same top bar. **Behaviour change:** a signed-out `/about` used to show the sign-in page. Help stays owner-only.
- **The sign-in page** gains a "Little Homey" link back to `/`, so a visitor who pressed Sign in can return to the marketing page.
- **Unchanged:** the signed-in header, the Help page (still owner-only), the About page's other text, the backend, and the API.

Ladder: none (no schema or generator change). Agents touched: none. The **render guard** and the **bpy allow-list** are **not affected**. The page shows no model, prompt, token or cost, and it calls no API besides the existing `/auth/me` check.

Estimate: about 45 minutes:
- page and routing, about 25 minutes;
- tests, about 10 minutes;
- checks and browser pass, about 10 minutes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`:
  - "The Studio is an owner-only single-page app": a signed-out visit to `/` shows the marketing page instead of the sign-in page;
  - "An About page explains the app in plain words": a signed-out `/about` shows the About page instead of the sign-in page, and the About page no longer lists the crew;
  - added: "A marketing page greets signed-out visitors".

## Impact

- `frontend/src/routes/About.tsx`: the crew section and `CREW` move to `Crew.tsx`.
- New `frontend/src/routes/Crew.tsx` (the crew page).
- New `frontend/src/routes/Landing.tsx` and `Landing.test.tsx`; new `frontend/public/homey.jpg`.
- `frontend/src/App.tsx`: explicit `/` and `/crew` routes (Landing when signed out, `HOME` when signed in; the crew page either way), and `/about` open to visitors under the top bar, ahead of the `*` catch-all.
- `frontend/src/routes/Login.tsx`: a brand link to `/`.
- `frontend/src/routes/About.test.tsx`: the "Signed out" test now expects the About page; the crew test becomes "Crew moved to its own page".
- `frontend/src/App.test.tsx`: any expectation that a signed-out `/` shows the sign-in page changes.
- `.gitignore`: `/docs/Little Homey Landing page/` (done with this request).
- No backend, migration or proxy change.
