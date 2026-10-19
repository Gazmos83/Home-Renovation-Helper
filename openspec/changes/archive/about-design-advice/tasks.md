## 1. Frontend

- [x] 1.1 Add "Advice you can check" and then "Stick to your budget" to `frontend/src/routes/About.tsx`, after "Your measurements stay put". Verify with `About.test.tsx` cases for both, with "Stick to your budget" last and no "certified" or "safe to build"
- [x] 1.2 Lay the points out as centred boxes with lucide icons, three per row (`lg:grid-cols-3`, two at `sm`, one on a phone); `About.test.tsx` checks the order, the box, the icon and the grid
- [x] 1.3 Colour from the app's tokens: a `primary` top trim on each box, the box shaded from `card` to `accent` with a primary-tinted shadow, and the icon in a filled `primary` circle; checked in light and dark mode
- Note 2026-10-19: the owner asked to skip the proposal step; the wording was not approved separately.

## 2. Checks

- [x] 2.1 `pnpm lint`, `pnpm test`, `pnpm build`
- [x] 2.2 Browser pass (headless Chrome, 2026-10-19): `/about` signed in and signed out shows six boxes in two rows of three, the budget one last; no sideways scroll at 390 px
