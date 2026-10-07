import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

/** What Intake needs from a blueprint or a hand sketch (studio-ui; Intake's record_plan fields). */
export const MEASUREMENTS = [
  "Each room's name.",
  "The length of every wall, edge by edge, going round the room in one direction.",
  "Every corner angle that is not 90°.",
  "The ceiling height.",
  "The wall thickness.",
  "Every door and window: the wall it is on, its offset from that wall's starting corner, its width and its height, and for a window its sill height.",
  "A scale reference: a dimension line, a printed area or a known door width.",
  "All rooms of one apartment drawn in one plan frame, so the walls line up.",
];

/** A worked example: one room, its walls numbered from the starting corner, one door. */
function ExampleRoom() {
  return (
    <svg viewBox="0 0 320 240" role="img" aria-labelledby="example-room-title" className="w-full max-w-sm text-foreground">
      <title id="example-room-title">
        Example: a hall of 4000 by 3000 mm, walls numbered clockwise from the top-left corner, with a 900 mm door on wall 1
        starting 500 mm from the corner
      </title>
      <rect x="40" y="40" width="240" height="160" fill="none" stroke="currentColor" strokeWidth="6" />
      <line x1="70" y1="40" x2="124" y2="40" stroke="var(--background)" strokeWidth="8" />
      <path d="M70 40 A54 54 0 0 1 124 94" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" />
      <circle cx="40" cy="40" r="5" fill="currentColor" />
      <g fontSize="12" fill="currentColor" textAnchor="middle">
        <text x="160" y="28">wall 1 · 4000 mm</text>
        <text x="300" y="124" transform="rotate(90 300 124)">wall 2 · 3000 mm</text>
        <text x="160" y="222">wall 3 · 4000 mm</text>
        <text x="20" y="124" transform="rotate(-90 20 124)">wall 4 · 3000 mm</text>
        <text x="97" y="60">door 900</text>
        <text x="160" y="125">Hall · ceiling 2500 mm</text>
      </g>
      <text x="46" y="58" fontSize="10" fill="currentColor">start</text>
    </svg>
  );
}

export default function Help() {
  return (
    <Page>
      <h1>Help</h1>
      <section className={`${cardClass} space-y-3`} aria-label="Preparing a blueprint">
        <h2>Preparing a blueprint or a sketch</h2>
        <p>
          Intake reads a plan or a hand sketch and turns it into rooms. A clear photo of a printed plan works, and so does a
          neat sketch on paper. Write every figure in millimetres, and go round each room from one corner, always in the same
          direction.
        </p>
        <h3>The measurements Intake needs</h3>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {MEASUREMENTS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <h3>An example</h3>
        <ExampleRoom />
        <p>
          Here the walls are numbered from the starting corner, going clockwise. The door is on wall 1, 500 mm from the start,
          900 mm wide and 2100 mm high.
        </p>
      </section>
      <section className={`${cardClass} space-y-2`} aria-label="Files">
        <h2>Files a conversation accepts</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Plans and photos: PNG or JPEG images.</li>
          <li>Notes: Markdown (.md) or plain text (.txt). If a note disagrees with what is already recorded, Intake asks which figure holds.</li>
          <li>Designs: a design file (.json) exported from a piece or made from the import template.</li>
        </ul>
      </section>
    </Page>
  );
}
