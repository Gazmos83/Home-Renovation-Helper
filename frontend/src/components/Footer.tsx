import { Link } from "react-router-dom";

/**
 * The line every page ends with (little-homey-brand-about-footer): the name and year, the Studio's
 * version and the commit it was built from ("dev" when unknown), and About for a signed-in owner.
 * Fixed to the bottom of the screen; the body's bottom padding and the full-height columns leave room
 * for it, so it never covers the composer or a pane.
 */
export function Footer({ signedIn }: { signedIn: boolean }) {
  return (
    <footer className="fixed inset-x-0 bottom-0 z-40 h-[var(--footer-h)] border-t bg-card text-xs text-muted-foreground">
      <div className="mx-auto flex h-full max-w-5xl items-center gap-x-3 overflow-hidden px-4 whitespace-nowrap sm:px-6">
        <span>© 2026 Little Homey</span>
        <span>
          v{__APP_VERSION__} · {__APP_BUILD__}
        </span>
        {signedIn && (
          <Link to="/about" className="underline">
            About
          </Link>
        )}
      </div>
    </footer>
  );
}
