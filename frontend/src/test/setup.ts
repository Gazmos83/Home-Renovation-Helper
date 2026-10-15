import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { resetWorkspaceLayout } from "../lib/workspaceLayout";
import { installMatchMedia } from "./media";

beforeEach(installMatchMedia);
// Each test starts with nothing remembered in the browser, and on the default Workspace layout, which
// lives in memory as well.
beforeEach(() => {
  window.localStorage.clear();
  resetWorkspaceLayout();
});

// jsdom has no ResizeObserver. Like a browser, this one reports each element's size once when it is first
// observed (the resizable panels lay themselves out from that report), and never again.
class OnceResizeObserver {
  constructor(private callback: ResizeObserverCallback) {}
  observe(target: Element) {
    queueMicrotask(() => {
      const rect = target.getBoundingClientRect();
      const size = [{ inlineSize: rect.width, blockSize: rect.height }];
      this.callback(
        [{ target, contentRect: rect, borderBoxSize: size, contentBoxSize: size, devicePixelContentBoxSize: size }] as ResizeObserverEntry[],
        this as unknown as ResizeObserver,
      );
    });
  }
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= OnceResizeObserver as unknown as typeof ResizeObserver;

// jsdom lays nothing out: every element measures 0 × 0 at (0, 0), where user-event also clicks. The resizable
// panels lay themselves out from their sizes, and take a press near a handle or a panel edge for the start of a
// drag, so every click inside the Workspace would be taken. Their group and everything in it are given a size and
// measured off-screen instead.
const inGroup = (element: Element) => element.closest("[data-group]") !== null;
const measure = Element.prototype.getBoundingClientRect;
Element.prototype.getBoundingClientRect = function (this: Element) {
  if (inGroup(this)) {
    return { x: -10000, y: -10000, left: -10000, top: -10000, right: -9000, bottom: -9200, width: 1000, height: 800, toJSON: () => ({}) } as DOMRect;
  }
  return measure.call(this);
};
for (const [name, size] of [["offsetWidth", 1000], ["offsetHeight", 800]] as const) {
  const real = Object.getOwnPropertyDescriptor(HTMLElement.prototype, name);
  Object.defineProperty(HTMLElement.prototype, name, {
    configurable: true,
    get(this: HTMLElement) {
      return inGroup(this) ? size : (real?.get?.call(this) ?? 0);
    },
  });
}
