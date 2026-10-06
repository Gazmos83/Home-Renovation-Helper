import type { ReactNode } from "react";

export function Page({ children }: { children: ReactNode }) {
  return <main className="mx-auto max-w-5xl space-y-4 px-4 py-8 sm:px-6">{children}</main>;
}
