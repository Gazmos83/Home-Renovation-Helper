/**
 * jsdom has no `matchMedia`. This stub answers `(min-width: Npx)` and `(max-width: Npx)` from a screen width
 * that tests set with `setScreenWidth`; it starts at 1280 px (a laptop) before every test.
 */
type Listener = () => void;

let width = 1280;
const listeners = new Set<Listener>();

function matches(query: string): boolean {
  const min = /min-width:\s*(\d+)px/.exec(query);
  const max = /max-width:\s*(\d+)px/.exec(query);
  return (!min || width >= Number(min[1])) && (!max || width <= Number(max[1]));
}

export function setScreenWidth(px: number): void {
  width = px;
  for (const listener of listeners) listener();
}

export function installMatchMedia(): void {
  width = 1280;
  listeners.clear();
  window.matchMedia = (query: string) =>
    ({
      media: query,
      get matches() {
        return matches(query);
      },
      onchange: null,
      addEventListener: (_type: string, listener: Listener) => listeners.add(listener),
      removeEventListener: (_type: string, listener: Listener) => listeners.delete(listener),
      addListener: (listener: Listener) => listeners.add(listener),
      removeListener: (listener: Listener) => listeners.delete(listener),
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}
