import type { ReactNode } from "react";
import { Laptop, Lightbulb, PackageOpen, PiggyBank, Ruler, WandSparkles, type LucideIcon } from "lucide-react";
import { Page } from "@/components/Page";

/** One boxed point of the About page, with its icon. */
const SECTIONS: { title: string; icon: LucideIcon; body: ReactNode }[] = [
  {
    title: "Design on a low-powered computer",
    icon: Laptop,
    body: (
      <>
        Most 3D tools need an expensive graphics card. Little Homey makes quick preview pictures on the computer you already
        have. Only when you ask for a high-quality picture does it take longer, and it always tells you how long first.
      </>
    ),
  },
  {
    title: "The magic is in the revision",
    icon: WandSparkles,
    body: (
      <>
        Start from a piece you like, from a shop&apos;s website or a picture, and tell the assistant what you&apos;d change:
        &ldquo;make it 10 cm wider&rdquo;, &ldquo;add a drawer&rdquo;, &ldquo;oak instead of white&rdquo;. It revises the
        piece, checks it against what you asked for, and shows you the new version. Keep going until it&apos;s right. Every
        version is kept, so you can always go back.
      </>
    ),
  },
  {
    title: "Take your furniture anywhere",
    icon: PackageOpen,
    body: (
      <>
        When a piece is ready, download it and add it to a 3D model of your home that you already have. Or place it in a
        room right here in Little Homey, with your blueprint and your other furniture.
      </>
    ),
  },
  {
    title: "Your measurements stay put",
    icon: Ruler,
    body: (
      <>
        Many AI picture tools redraw a room each time you ask for a change. Along the way, things quietly drift: a shelf gets
        shorter, a wall moves, an open cubby suddenly has a door. Little Homey never redraws your furniture from a picture.
        Every piece is built from its exact measurements, and every picture shows that same model. A change happens only when
        you ask for it, and you see it in the new version. So what you see is what you can build.
      </>
    ),
  },
  {
    title: "Advice you can check",
    icon: Lightbulb,
    body: (
      <>
        Ask for advice while you design. Little Homey checks your piece and its place in the room against design rules taken
        from published guidelines: enough space to walk past, room for a door to swing, how far a shelf can span, how many
        brackets it needs. When something is off, it tells you which rule, what it measured and where the rule comes from.
        Ask whether a shelf will sag or what it can hold, and you get the sums and the source behind the answer. When the
        facts aren&apos;t there, Little Homey says it can&apos;t be sure and asks for what&apos;s missing, instead of
        guessing. For anything that could fall or tip, like wall cabinets or a fold-down bed, it tells you what still needs
        a qualified person&apos;s check.
      </>
    ),
  },
  {
    title: "Stick to your budget",
    icon: PiggyBank,
    body: (
      <>
        Tell Little Homey your budget when you describe a piece, and it keeps that number in mind while you design. When a
        piece is ready, it prices it from your DIY store&apos;s real prices: the boards you need to buy, fitted so as little
        as possible goes to waste, with the offcuts you already have used first, plus hardware, edging and cutting. If a
        price is missing, it tells you which one instead of making it up, so the total you see is a total you can trust.
      </>
    ),
  },
];

/** What Little Homey is for, in plain words (little-homey-brand-about-footer), one centred box per point, three to a row. */
export default function About() {
  return (
    <Page wide>
      <article className="mx-auto max-w-6xl space-y-6 text-center">
        <h1>About Little Homey</h1>
        <p className="mx-auto max-w-2xl">
          <strong>Little Homey is your home renovation assistant.</strong> It helps you design furniture and rooms for your
          own home, and shows them to you as 3D pictures, all on an ordinary laptop. You don&apos;t need a powerful computer
          or any 3D skills.
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map(({ title, icon: Icon, body }) => (
            <section
              key={title}
              aria-label={title}
              // The app's own colours: a primary trim on top, and a card shaded towards the accent with a tinted shadow for depth.
              className="flex flex-col items-center gap-3 rounded-xl border border-primary/20 border-t-4 border-t-primary bg-linear-to-b from-card to-accent p-6 text-card-foreground shadow-lg shadow-primary/15"
            >
              <span className="flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md shadow-primary/30" aria-hidden="true">
                <Icon className="size-6" />
              </span>
              <h2 className="text-lg leading-tight">{title}</h2>
              <p className="text-sm">{body}</p>
            </section>
          ))}
        </div>
      </article>
    </Page>
  );
}
