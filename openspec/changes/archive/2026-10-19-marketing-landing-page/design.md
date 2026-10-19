## Context

- **Mock-up** (`docs/Little Homey Landing page/7uBlkCMz2029wmp9-grok-workspace/src/routes/index.tsx`, 55 lines; screenshot `screenshots/app-builder-built.png`):
  - a dark top bar with a sparkle icon and "Little Homey", with a coral rule under it;
  - a two-column hero: the line "A small brand", the headline "Hello from Homey", a paragraph, a teal "Say hello" pill, and `homey.jpg`;
  - a cream closing card: "Home feels better with a little help." / "Little Homey".
  - It uses its own palette (charcoal, cream, ink, coral, teal) and the Baloo 2 and Nunito fonts from Google Fonts.
- **App today** (`frontend/src/App.tsx`):
  - `/` has no route of its own; the `*` catch-all sends a signed-out visitor to `/login` and a signed-in owner to `HOME` (`/studio/workspace`).
  - The header renders only when signed in. The `Footer` renders on every page and is fixed to the bottom; `body` has `padding-bottom: var(--footer-h)`.
  - `HouseIcon` is the brand icon. The theme tokens are in `frontend/src/index.css`, with light and dark modes.

## Goals / Non-Goals

**Goals:**
- A signed-out visitor at `/` sees what Little Homey is and a clear way to sign in.
- The page matches the rest of the app's look, in light and dark mode, at phone and laptop widths.

**Non-Goals:**
- The mock-up's palette, fonts, sparkle icon or Open Graph image (owner chose "app theme + mascot", 2026-10-19).
- Public About, Help, pricing or legal pages; sign-up; a contact form.
- Porting the mock-up's framework, scripts or auth.

## Decisions

1. **One explicit `/` route.** `signedIn ? <Navigate to={HOME} replace /> : <Landing />`. The catch-all still goes to `/login` when signed out, so deep links keep their sign-in redirect. *Alternative:* send every signed-out address to `/`. Rejected because it adds a click before every deep link and changes several existing scenarios.
2. **The page has its own top bar** (the signed-in header is hidden when signed out). It uses the same height, `bg-card` and `border-b` as the app header, with `HouseIcon` + "Little Homey" at the left and "Meet the crew" (decision 6), "About" (decision 7) and "Sign in" links at the right. At phone width the links tighten and the bar scrolls inside itself, like the signed-in header, so the page never scrolls sideways.
3. **Theme tokens only.** The hero line uses `text-primary`, the button is the existing `Button` (`asChild` around a `Link`), and the closing card uses `cardClass`/`bg-muted`. No new CSS variables, fonts or packages.
4. **Mascot as a static file.** `frontend/public/homey.jpg`, served at `/homey.jpg`, has `alt` text from the mock-up, `decoding="async"`, and width and height attributes to avoid layout shift. The image has a light cream background baked in, so in dark mode it sits on a `rounded-xl` frame and is not recoloured.
5. **The sign-in page links home.** A small `HouseIcon` + "Little Homey" link above "Sign in", to `/`.
6. **Meet the crew on its own page** (owner, 2026-10-19, replacing an earlier section on the marketing page). "Meet the crew" in the top bar, beside "Sign in", opens `/crew`. The page uses the same top bar (`SiteBar`, exported from `Landing.tsx`; the link is marked current there) and holds the crew list (`CREW`, moved from `About.tsx`, which no longer lists the crew; owner, 2026-10-19). A signed-in owner at `/crew` sees the same page under the owner's header; the owner's header has no crew link (not asked for). *Alternative:* a crew section on the marketing page. Replaced by the owner.
8. **Archived before `meet-the-crew`** (2026-10-19). Both changes modify "An About page explains the app in plain words"; this change's version drops the crew paragraph that `meet-the-crew` adds. `meet-the-crew` was still waiting on its browser pass, so this change was archived first and the superseded About requirement was removed from `meet-the-crew`'s delta, so archiving it later cannot bring the crew back to About.
7. **About opens to visitors** (owner, 2026-10-19). `/about` signed out renders the same `About` under `SiteBar` instead of redirecting to sign-in; its text already avoids model, prompt, token and engine names. Help stays owner-only. The signed-out footer keeps no About link; the top bar has one. *Alternatives:* a visitor-only About without the crew section, or an About link to sign-in. The owner chose the full page.
9. **Crew character art** (owner, 2026-10-19). Each crew entry shows the owner's picture of that member beside the name and job, from `frontend/public/crew/<name>.jpg` (copied from the gitignored `docs/Little Homey Landing page/`, renamed without spaces); Little Homey reuses `/homey.jpg`. Same treatment as the mascot (decision 4): width and height attributes, `decoding="async"`, plus `loading="lazy"`, alt text naming the member, a `rounded-lg border` frame, not recoloured in dark mode. The pictures are used as supplied (about 0.3 MB each), not re-encoded.

## Draft texts (owner review)

The mock-up's eyebrow "A small brand" is placeholder text from the generator. The draft replaces it with the owner's tagline from 2026-10-18. The owner approved every text on 2026-10-19.

- Line above the headline: **Your home renovation helpers** (owner, 2026-10-19)
- Headline: **Hello from Little Homey and his crew** (owner, 2026-10-19)
- Paragraph: **They're ready to help build custom furniture that makes a house feel like a home.** (owner, 2026-10-19)
- Button: **Sign in** (owner, 2026-10-19)
- Top-bar links: **Meet the crew**, **About** (owner, 2026-10-19)
- Crew page heading: **Meet the crew** (owner, 2026-10-19)
- Closing card: **We help you make your house a home.** / **Little Homey** (owner, 2026-10-19)
- Image alt: **Little Homey, a cartoon kid in a teal beanie and brown overalls, with a tape measure in the pocket**

## Risks / Trade-offs

- [The mascot JPEG's baked-in background looks like a light box in dark mode] → It sits in a rounded frame, so it reads as a picture card. The browser pass checks it in dark mode.
- [Someone may expect the marketing page to explain the features] → The owner can extend the copy later; the page is built from the mock-up as asked.
