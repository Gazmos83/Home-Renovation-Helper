/** Little Homey's crew, one entry per agent, as the owner meets them (meet-the-crew; on its own page since marketing-landing-page), each with the owner's character art. */
const CREW = [
  {
    name: "Little Homey",
    image: { src: "/homey.jpg", width: 1045, height: 1568, alt: "Little Homey, a cartoon kid in a teal beanie and brown overalls, with a tape measure in the pocket" },
    job: "The friendly face of the crew. Listens to what you want, then shouts for the right friend to take it on. If it's not sure who, it asks you.",
  },
  {
    name: "Lil' Worm",
    image: { src: "/crew/lil-worm.jpg", width: 784, height: 1168, alt: "Lil' Worm, a little figure in a yellow bobble hat and brown overalls, pulling out a tape measure" },
    job: "Wriggles into every corner of your home with a tape measure. Reads your floor plans and room photos, writes down every wall, window and ceiling height, and won't let anyone start until the numbers are right.",
  },
  {
    name: "Lil' Glitty",
    image: { src: "/crew/lil-glitty.jpg", width: 784, height: 1168, alt: "Lil' Glitty, in a sparkly pink beanie and paint-splashed overalls, holding a drawing of a shelf" },
    job: "The designer with the sparkle. Turns your wish into a real piece (sizes, shelves, drawers, wood) and makes the list of boards to cut. Checks that it fits your room, and happily redoes it as often as you like.",
  },
  {
    name: "Little Beam",
    image: { src: "/crew/little-beam.jpg", width: 784, height: 1168, alt: "Little Beam, in a blue beanie and brown overalls, carrying a wooden beam across the shoulders" },
    job: "The crew's strength checker. Tells you how much a shelf can hold, whether it will sag and how it should hang on the wall. If Beam isn't sure, Beam says so.",
  },
  {
    name: "Muscles",
    image: { src: "/crew/muscles.jpg", width: 784, height: 1168, alt: "Muscles, in a red beanie and brown overalls, holding a hammer" },
    job: "Does the heavy lifting. Builds your piece in 3D from Glitty's plans and spins it round so you can see it from every side.",
  },
  {
    name: "Bulbs",
    image: { src: "/crew/bulbs.jpg", width: 784, height: 1168, alt: "Bulbs, in a yellow beanie topped with a light bulb, holding a glowing bulb in each hand" },
    job: "The bright spark. Adds real-looking wood, fabric and light for the extra-pretty pictures.",
  },
  {
    name: "Mr. Lookback",
    image: { src: "/crew/mr-lookback.jpg", width: 784, height: 1168, alt: "Mr. Lookback, in a grey beanie and blue overalls, peering through a magnifying glass" },
    job: "Never lets anything slide. Holds every picture up next to what you asked for and points out anything that doesn't match. He only looks, he never touches.",
  },
  {
    name: "Money Bags",
    image: { src: "/crew/money-bags.jpg", width: 784, height: 1168, alt: "Money Bags, a green money bag in a beanie and blue overalls, holding a clipboard of offcuts and prices" },
    job: "Knows what everything costs. Looks up prices at toom, adds up the boards and keeps an eye on the offcuts you already have.",
  },
];

/** The crew page at `/crew`, opened from the visitor's top bar (marketing-landing-page). */
export default function Crew() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl font-bold leading-tight">Meet the crew</h1>
      <p className="mt-3 max-w-2xl text-base text-muted-foreground">
        Little Homey doesn&apos;t work alone. It&apos;s a crew of friends who each have one job, and they love it. You
        chat, they get to work.
      </p>
      <ul className="mt-8 mb-12 grid gap-4 sm:grid-cols-2" aria-label="The crew">
        {CREW.map((member) => (
          <li key={member.name} className="flex items-start gap-4 rounded-xl border bg-card p-4 text-card-foreground">
            <img
              src={member.image.src}
              width={member.image.width}
              height={member.image.height}
              loading="lazy"
              decoding="async"
              alt={member.image.alt}
              className="h-auto w-24 shrink-0 rounded-lg border sm:w-28"
            />
            <div>
              <strong>{member.name}</strong>
              <p className="mt-1 text-muted-foreground">{member.job}</p>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
