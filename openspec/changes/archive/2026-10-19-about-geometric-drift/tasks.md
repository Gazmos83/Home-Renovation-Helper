## 0. Wording

- [x] 0.1 The owner approves the section's heading and text in `proposal.md`

## 1. Frontend

- [x] 1.1 Add the "Your measurements stay put" section to `frontend/src/routes/About.tsx`, after "Take your furniture anywhere", with the approved text. Verify with an `About.test.tsx` case for "Measurements stay put" and the existing no-technical-terms check.

## 2. Checks

- [x] 2.1 `pnpm lint`, `pnpm test`, `pnpm build`
- [x] 2.2 Browser pass: `/about` signed in and signed out shows the new section last
