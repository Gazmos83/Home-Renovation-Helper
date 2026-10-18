import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

test("a build with no readable commit shows the version followed by dev (Unknown build)", async () => {
  vi.stubGlobal("__APP_BUILD__", "dev");
  vi.stubGlobal("__APP_VERSION__", "0.1.0");
  const { Footer } = await import("./Footer");
  render(<MemoryRouter><Footer signedIn={false} /></MemoryRouter>);
  expect(screen.getByRole("contentinfo")).toHaveTextContent("v0.1.0 · dev");
});
