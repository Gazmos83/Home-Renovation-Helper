import { Page } from "@/components/Page";

/** What Little Homey is for, in plain words (little-homey-brand-about-footer). */
export default function About() {
  return (
    <Page>
      <article className="max-w-2xl space-y-4">
        <h1>About Little Homey</h1>
        <p>
          <strong>Little Homey is your home renovation assistant.</strong> It helps you design furniture and rooms for your
          own home, and shows them to you as 3D pictures, all on an ordinary laptop. You don&apos;t need a powerful computer
          or any 3D skills.
        </p>
        <h2>Design on a low-powered computer</h2>
        <p>
          Most 3D tools need an expensive graphics card. Little Homey makes quick preview pictures on the computer you
          already have. Only when you ask for a high-quality picture does it take longer, and it always tells you how long
          first.
        </p>
        <h2>The magic is in the revision</h2>
        <p>
          Start from a piece you like, from a shop&apos;s website or a picture, and tell the assistant what you&apos;d
          change: &ldquo;make it 10 cm wider&rdquo;, &ldquo;add a drawer&rdquo;, &ldquo;oak instead of white&rdquo;. It
          revises the piece, checks it against what you asked for, and shows you the new version. Keep going until it&apos;s
          right. Every version is kept, so you can always go back.
        </p>
        <h2>Take your furniture anywhere</h2>
        <p>
          When a piece is ready, download it and add it to a 3D model of your home that you already have. Or place it in a
          room right here in Little Homey, with your blueprint and your other furniture.
        </p>
        <h2>Your measurements stay put</h2>
        <p>
          Many AI picture tools redraw a room each time you ask for a change. Along the way, things quietly drift: a shelf
          gets shorter, a wall moves, an open cubby suddenly has a door. Little Homey never redraws your furniture from a
          picture. Every piece is built from its exact measurements, and every picture shows that same model. A change
          happens only when you ask for it, and you see it in the new version. So what you see is what you can build.
        </p>
      </article>
    </Page>
  );
}
