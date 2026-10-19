## 0. Owner review

- [x] 0.1 The owner approves or edits the draft texts in `design.md`, especially the line above the headline. Record the decision here.
  - 2026-10-19: owner set the headline "Hello from Little Homey and his crew", the paragraph "They're ready to help build custom furniture that makes a house feel like a home." ("make" corrected to "makes" at the owner's request) and the button "Sign in", and kept "Your home renovation assistant" above the headline.
  - 2026-10-19 (later): owner changed the line above the headline to "Your home renovation helpers" and the closing card to "Make your little house a home with a little help", and asked for a "Meet the crew" link to a crew section on this page (design.md decision 6).
  - 2026-10-19 (later): owner changed the closing card to "We help you make your house a home." and moved the crew to its own page, opened from "Meet the crew" beside "Sign in". Then asked for an "About" link beside "Meet the crew", with About open to visitors, and for the Meet the crew section to leave the About page.

## 1. Gitignore

- [x] 1.1 Add `/docs/Little Homey Landing page/` to `.gitignore` (done 2026-10-19 with the request); `git status` no longer lists it.

## 2. Marketing page

- [x] 2.1 Copy the mock-up's `public/homey.jpg` to `frontend/public/homey.jpg`.
- [x] 2.2 Add `frontend/src/routes/Landing.tsx` with the top bar, hero and closing card (design.md decisions 2–4, approved texts), using theme tokens, `Button`, `HouseIcon` and `Link` only.
- [x] 2.3 In `frontend/src/App.tsx`, add `<Route path="/" …>` (Landing signed out, `Navigate` to `HOME` signed in) before the catch-all.
- [x] 2.4 In `frontend/src/routes/Login.tsx`, add the `HouseIcon` + "Little Homey" link to `/`.
- [x] 2.5 Add a "Meet the crew" link beside "Sign in" in the top bar (`SiteBar`) that opens a new `frontend/src/routes/Crew.tsx` at `/crew`, listing the About page's exported `CREW`; signed in, `/crew` goes to `/about` (owner, 2026-10-19; design.md decision 6).
- [x] 2.6 Add an "About" link beside "Meet the crew" in `SiteBar`, and in `App.tsx` show `/about` signed out under `SiteBar` instead of redirecting to sign-in (owner, 2026-10-19; design.md decision 7). Tighten the links and let the bar scroll inside itself at phone width.
- [x] 2.7 Move `CREW` and the "Meet the crew" section out of `About.tsx` into `Crew.tsx`; signed in, `/crew` shows the crew page under the owner's header (owner, 2026-10-19; design.md decisions 6 and 8).
- [x] 2.8 Copy the owner's crew art to `frontend/public/crew/` and show each member's picture beside their entry in `Crew.tsx`, Little Homey with `/homey.jpg` (owner, 2026-10-19; design.md decision 9).

## 3. Tests

- [x] 3.1 Add `Landing.test.tsx` for "Visitor sees the marketing page", "Sign in from the marketing page", "Back from the sign-in page", "Signed-in owner at the root" and "Deep link while signed out". Include a check that the page text has none of: model, prompt, token, cost.
- [x] 3.2 Update `App.test.tsx` wherever a signed-out `/` expected the sign-in page. Verify with `pnpm test`.
- [x] 3.3 Test "Meet the crew from the marketing page" (top-bar links in order, the crew page with About's names in order, the link marked current, Sign in from there) and "Signed-in owner at the crew page". The no-model-words check allows Money Bags' "what everything costs" (furniture prices, not model-call costs).
- [x] 3.4 Test "About for a visitor" in `Landing.test.tsx`, and change `About.test.tsx`'s "Signed out" test to expect the About page (an explicit behaviour change, asked for by the owner).
- [x] 3.5 `About.test.tsx`: replace the crew test with "Crew moved to its own page"; the crew page test checks each job description, and "Signed-in owner at the crew page" expects the crew page.
- [x] 3.6 "Meet the crew from the marketing page" also checks each entry's picture source, in order, and that its alt text names the member.

## 4. Checks

- [x] 4.1 Run `pnpm lint && pnpm test && pnpm build` in `frontend/`. No backend change, so pytest and ruff are not needed.
- [x] 4.2 Browser pass (owner: passed, 2026-10-19, including the crew pictures), with **no render tier**, at 1280 × 800 and 360 × 780, in light and dark mode:
  - signed out, `/` shows the marketing page with the mascot and the footer;
  - "Meet the crew" opens the crew page, which reads well in both modes with each picture beside its member, and the top bar fits at phone width;
  - "About" opens the About page signed out, under the same top bar, with no crew section;
  - both Sign in controls open the sign-in page, and its "Little Homey" link returns;
  - signing in opens the Workspace, and `/` while signed in opens the Workspace;
  - `/studio/pieces` signed out shows the sign-in page;
  - nothing scrolls sideways at phone width, and the mascot reads well in dark mode.
