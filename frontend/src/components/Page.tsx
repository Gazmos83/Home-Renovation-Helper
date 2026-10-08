import type { ReactNode } from "react";

/** The page body. `wide` drops the centred width cap, for a page that lays out its own columns. */
export function Page({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <main className={wide ? "min-w-0 flex-1 space-y-4 px-4 py-8 sm:px-6" : "mx-auto max-w-5xl space-y-4 px-4 py-8 sm:px-6"}>
      {children}
    </main>
  );
}
