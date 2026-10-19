## Why

The owner asked on 2026-10-19 for an About page section on design and engineering advice. The app already gives both. Design rules come from cited guidelines, are checked in code and are shown as warnings with their source (`design-guidelines`). Engineering answers show their sources and maths, and say "not verified" when evidence is missing (`engineering-safety`). The About page does not mention either.

## What Changes

- The About page gains a section, after "Your measurements stay put", on design and engineering advice. Proposed wording (the owner asked to skip the proposal, 2026-10-19):

  > **Advice you can check**
  >
  > Ask for advice while you design. Little Homey checks your piece and its place in the room against design rules taken from published guidelines: enough space to walk past, room for a door to swing, how far a shelf can span, how many brackets it needs. When something is off, it tells you which rule, what it measured and where the rule comes from. Ask whether a shelf will sag or what it can hold, and you get the sums and the source behind the answer. When the facts aren't there, Little Homey says it can't be sure and asks for what's missing, instead of guessing. For anything that could fall or tip, like wall cabinets or a fold-down bed, it tells you what still needs a qualified person's check.

- A second section, last, on sticking to a budget, asked for on the same day:

  > **Stick to your budget**
  >
  > Tell Little Homey your budget when you describe a piece, and it keeps that number in mind while you design. When a piece is ready, it prices it from your DIY store's real prices: the boards you need to buy, fitted so as little as possible goes to waste, with the offcuts you already have used first, plus hardware, edging and cutting. If a price is missing, it tells you which one instead of making it up, so the total you see is a total you can trust.

- The page is laid out as centred boxes, each with an icon, three to a row (asked for on the same day: first four to a row, then three with centred text).
- No technical terms, as the About requirement already demands.

Ladder step: none. Agents touched: none. Render guard and `bpy` allow-list: not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: the About page explains two more points: design and engineering advice is checked against cited sources and says when it cannot be sure, and pricing uses real store prices and never guesses.

## Impact

- `frontend/src/routes/About.tsx` and its test.
