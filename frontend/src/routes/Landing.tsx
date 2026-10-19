import { Link, NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { cardClass } from "@/components/ui/card";
import { HouseIcon } from "@/components/HouseIcon";

const topLinkClass = (active: boolean) =>
  cn(
    "shrink-0 rounded-md px-2 py-1.5 sm:px-3 text-sm font-medium whitespace-nowrap transition-colors hover:bg-accent",
    active ? "bg-accent text-accent-foreground" : "text-muted-foreground",
  );

/** The top bar of the signed-out pages: the name at the left, Meet the crew, About and Sign in at the right. */
export function SiteBar() {
  return (
    <header className="h-[var(--header-h)] border-b bg-card">
      <nav aria-label="Site" className="flex h-full items-center gap-1 overflow-x-auto px-4 sm:px-6">
        <Link to="/" className="mr-auto flex shrink-0 items-center gap-2 pr-2 font-semibold whitespace-nowrap">
          <HouseIcon />
          Little Homey
        </Link>
        <NavLink to="/crew" className={({ isActive }) => topLinkClass(isActive)}>
          Meet the crew
        </NavLink>
        <NavLink to="/about" className={({ isActive }) => topLinkClass(isActive)}>
          About
        </NavLink>
        <Link to="/login" className={topLinkClass(false)}>
          Sign in
        </Link>
      </nav>
    </header>
  );
}

/** The marketing page a signed-out visitor sees at `/` (marketing-landing-page). */
export default function Landing() {
  return (
    <>
      <SiteBar />
      <main className="mx-auto max-w-5xl px-4 sm:px-6">
        <section className="grid items-center gap-10 py-12 md:grid-cols-2 md:gap-16 md:py-20">
          <div>
            <p className="text-lg font-semibold text-primary">Your home renovation helpers</p>
            <h1 className="mt-2 text-4xl font-bold leading-tight md:text-5xl">Hello from Little Homey and his crew</h1>
            <p className="mt-5 max-w-md text-lg text-muted-foreground">
              They're ready to help build custom furniture that makes a house feel like a home.
            </p>
            <Button asChild size="lg" className="mt-8">
              <Link to="/login">Sign in</Link>
            </Button>
          </div>
          <img
            src="/homey.jpg"
            width={1045}
            height={1568}
            decoding="async"
            alt="Little Homey, a cartoon kid in a teal beanie and brown overalls, with a tape measure in the pocket"
            className="mx-auto h-auto w-full max-w-sm rounded-xl border"
          />
        </section>
        <section className={`${cardClass} mb-12 bg-muted px-8 py-10`}>
          <p className="text-3xl font-bold leading-tight">We help you make your house a home.</p>
          <p className="mt-3 text-muted-foreground">Little Homey</p>
        </section>
      </main>
    </>
  );
}
