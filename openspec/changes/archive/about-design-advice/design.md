## Context

`About.tsx` has an intro and four `h2` sections, the last being "Your measurements stay put". The About requirement forbids technical terms; the page test refuses "model name", "prompt", "token", "frame", "resolution", "Eevee" and "Cycles".

## Decisions

- **Placement.** The new section goes last, after "Your measurements stay put".
- **Promise only what exists.** The examples are rules the app already checks: passage, door swing, shelf span and bracket count (`design-guidelines`). The engineering sentences follow `engineering-safety`. Answers show their evidence, say when they cannot be sure ("NOT VERIFIED" in plain words), and name the qualified check that higher-risk pieces need. The section does not claim that anything is certified or safe to build.
- **No persona names.** The crew page introduces Little Beam. The About page speaks of Little Homey only, as it already does and as the "About does not list the crew" requirement keeps it.
- **Budget, honestly.** The budget is recorded in the brief and every agent reads it, but no code compares a pricing with it. So the section says the budget is "kept in mind" and describes pricing (`cut-list-pricing`): real store prices, packing, offcuts first, and missing prices named. It does not promise that a piece stays within budget.
