## Context

See proposal.md (Why). The current state the approach builds on:

- **`frontend/src/App.tsx`:**
  - The header is shown only when signed in, and is sticky with `h-[var(--header-h)]`.
  - It holds the brand link "Home Renovation" to `HOME`, then `links = [["/help", "Help"]]`, then `SignOut`.
  - The routes follow, and nothing is rendered after `<Routes>`.
- **Studio layout.** The sub-menu (`components/studio/SubMenu.tsx`) and the rail (`components/chat/Rail.tsx`) are sticky columns `h-[calc(100vh-var(--header-h))]`, so an in-flow footer sits below them and does not cut into their height.
- **Names and assets.**
  - `frontend/index.html` has `<title>Home Renovation Agents</title>` and no favicon, and `frontend/public/` does not exist.
  - `frontend/package.json` has version `0.1.0`.
  - `backend/app/main.py:323` has `title="Home Renovation Agents"`.
- **Tests and help.**
  - `frontend/src/App.test.tsx` asserts the header links (`["Home Renovation", "Help"]`, three places).
  - The help source names no app, so `help-center` is unchanged.

## Goals / Non-Goals

**Goals:**
- One name and one icon everywhere the owner sees the app.
- An About page a non-technical friend can read in a minute.
- A footer that tells the owner which build they are running.
- A README whose first screen explains the concept.

**Non-Goals:**
- Renaming the repository, the Python or npm packages, the database, or CLAUDE.md.
- A marketing site, a public (signed-out) About page, or legal pages. The owner chose name, year and version/build only (2026-10-18).
- Changing the Help center.

## Decisions

1. **Icon.**
   - One hand-drawn SVG: a house outline with a pitched roof and a small door, 24×24 viewBox, 2 px stroke.
   - It is stored as `frontend/public/favicon.svg` (served by Vite as `/favicon.svg`, linked from `index.html`), and as a `HouseIcon` React component using `stroke="currentColor"` for the header.
   - lucide's `House` was considered, since the project already uses lucide icons. It is acceptable as the header icon if the owner prefers, but a favicon file is needed either way. `TODO(user)`: replace with your own icon file later if you make one.

2. **Version and build.**
   - In `vite.config.ts`, `define` sets `__APP_VERSION__` from `package.json` and `__APP_BUILD__` from `git rev-parse --short HEAD`, run once with `execSync` inside a try/catch that falls back to `"dev"`.
   - The same `define` applies to Vitest, so tests see fixed values. In tests they are overridden to `"0.0.0"` and `"test"` through `test.define`.
   - Reading the commit at runtime from the API was rejected, because it would add a backend route for display only.

3. **Footer placement.**
   - `<Footer />` is rendered after `<Routes>` in `App.tsx`, for signed-in and signed-out states. The About link is shown only when signed in.
   - 2026-10-19, the owner: the footer is always frozen at the bottom of the page. It is `fixed bottom-0` with a height `--footer-h` (2.25rem, beside `--header-h` in `index.css`), one line that does not wrap.
   - So it never covers the chat input or the inspector, the body has `padding-bottom: var(--footer-h)`, and every full-height column subtracts it: the rail, its fly-out, the sub-menu, the Workspace panes and the tile grid. The panes shrink by that one line.

4. **Header layout.** 2026-10-19, the owner: the name and icon sit at the left edge of the header, and Help, About and Sign out at the right edge. The nav spans the full width (no `max-w-5xl`), and the three right-hand items share one `ml-auto` group.

5. **About route.** `/about` is gated like `/help` (signed out → `/login`), rendered by `routes/About.tsx` in the existing `Page` wrapper, with an Oswald heading (studio-ui "Page headings use Oswald").

6. **README.**
   - The new top section replaces only the title and the first paragraph.
   - The current purpose paragraph and the developer intro move under a "For developers" heading, followed by the existing sections, unchanged.
   - The table of contents links to the concept parts and to the first technical section.

## Draft texts for review (owner approves the wording before apply)

### About page (`/about`)

> # About Little Homey
>
> **Little Homey is your home renovation assistant.** It helps you design furniture and rooms for your own home, and shows them to you as 3D pictures, all on an ordinary laptop. You don't need a powerful computer or any 3D skills.
>
> ## Design on a low-powered computer
> Most 3D tools need an expensive graphics card. Little Homey makes quick preview pictures on the computer you already have. Only when you ask for a high-quality picture does it take longer, and it always tells you how long first.
>
> ## The magic is in the revision
> Start from a piece you like, from a shop's website or a picture, and tell the assistant what you'd change: "make it 10 cm wider", "add a drawer", "oak instead of white". It revises the piece, checks it against what you asked for, and shows you the new version. Keep going until it's right. Every version is kept, so you can always go back.
>
> ## Take your furniture anywhere
> When a piece is ready, download it and add it to a 3D model of your home that you already have. Or place it in a room right here in Little Homey, with your blueprint and your other furniture.

### README concept section

> # Little Homey
>
> *(house icon)* **Your home renovation assistant.**
>
> ## Contents
> - [Concept](#concept)
>   - [Create your furniture piece](#create-your-furniture-piece)
>   - [Create your room or home](#create-your-room-or-home)
>   - [Create a realistic render](#create-a-realistic-render)
> - [For developers](#for-developers)
>
> ## Concept
>
> Little Homey runs on your own computer, even one with little processing power. Its idea is simple: **find the furniture you want, customise it, then build it.**
>
> ### Create your furniture piece
> 1. **Find a piece you like.** A product on a furniture website, or a picture or render you've seen.
> 2. **Turn it into a package.** Download the design template from the Pieces page, and fill it in from the product page or picture (another AI chat can help).
> 3. **Import it.** Start a new conversation, attach the package and ask for the piece to be created.
> 4. **Customise it.** Ask for changes in your own words. Each change makes a new version you can inspect in 3D, with its cut list.
> 5. **Export it.** Download the finished piece to add to your own home model.
>
> ### Create your room or home
> 1. **Import your blueprint**, or a photo or sketch with measurements, in a conversation.
> 2. **Design the room** with pieces you made and models from your model library: place them, move them and check that everything fits.
>
> ### Create a realistic render
> 1. **Define the layout** with your room, your models and your pieces.
> 2. **Choose a design and lighting style** and ask for a realistic render. A quick preview is made right away; the high-quality picture is made only after you say yes, because it takes longer.
>
> ## For developers
> *(the existing purpose paragraph and the technical sections follow, unchanged)*

## Risks / Trade-offs

- [The build id is stale in a long-running `pnpm dev`] → It is read when Vite starts. It is good enough for a personal app, and restarting updates it.
- [The About text promises export] → The export already exists (version file downloads: GLB, blend and spec JSON in the Files tab), so the text describes current behaviour.
- [The README promises lighting styles] → Restyle variants exist (`config/styles.yaml`), and lamp lights are proposed in the same review batch. The text says "lighting style", which restyle covers today.

## Migration Plan

None. Front-end and docs only. The API title change affects only the `/docs` page.
