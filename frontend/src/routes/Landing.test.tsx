import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import App from "../App";
import { stubFetch } from "../test/fetchStub";

/** marketing-landing-page: what a signed-out visitor sees at `/`. */

function show(pathname: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[pathname]}><App /></MemoryRouter>
    </QueryClientProvider>,
  );
}

function signedOut() {
  return stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
}

test("a signed-out visit to / shows the marketing page (Visitor sees the marketing page)", async () => {
  const calls = signedOut();
  show("/");
  const heading = await screen.findByRole("heading", { level: 1, name: "Hello from Little Homey and his crew" });
  expect(screen.getByText("Your home renovation helpers")).toBeInTheDocument();
  expect(screen.getByText("They're ready to help build custom furniture that makes a house feel like a home.")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Little Homey, a cartoon kid/ })).toHaveAttribute("src", "/homey.jpg");
  expect(screen.getByText("We help you make your house a home.")).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "The crew" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Site" })).getByRole("link", { name: "Little Homey" })).toBeInTheDocument();
  expect(screen.getByRole("contentinfo")).toHaveTextContent("© 2026 Little Homey");
  expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
  const page = heading.closest("main") as HTMLElement;
  // Money Bags "knows what everything costs": furniture prices are fine, model-call costs are not.
  expect(page.textContent).not.toMatch(/\b(model|prompt|token)s?\b|\b(call|token|usage) costs?\b/i);
  expect(calls.map(([method, url]) => `${method} ${url}`).every((call) => call === "GET /auth/me")).toBe(true);
});

test("Meet the crew in the top bar opens the crew page (Meet the crew from the marketing page)", async () => {
  const calls = signedOut();
  const user = userEvent.setup();
  show("/");
  const nav = await screen.findByRole("navigation", { name: "Site" });
  expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Little Homey", "Meet the crew", "About", "Sign in"]);
  await user.click(within(nav).getByRole("link", { name: "Meet the crew" }));
  const heading = await screen.findByRole("heading", { level: 1, name: "Meet the crew" });
  const crew = within(screen.getByRole("list", { name: "The crew" })).getAllByRole("listitem");
  expect(crew.map((item) => item.querySelector("strong")?.textContent)).toEqual([
    "Little Homey", "Lil' Worm", "Lil' Glitty", "Little Beam", "Muscles", "Bulbs", "Mr. Lookback", "Money Bags",
  ]);
  for (const item of crew) expect(item.textContent!.length).toBeGreaterThan(40);
  // Each member's character art sits in their own entry (Crew character art).
  expect(crew.map((item) => within(item).getByRole("img").getAttribute("src"))).toEqual([
    "/homey.jpg", "/crew/lil-worm.jpg", "/crew/lil-glitty.jpg", "/crew/little-beam.jpg",
    "/crew/muscles.jpg", "/crew/bulbs.jpg", "/crew/mr-lookback.jpg", "/crew/money-bags.jpg",
  ]);
  for (const item of crew) {
    expect(within(item).getByRole("img")).toHaveAccessibleName(expect.stringContaining(item.querySelector("strong")!.textContent!));
  }
  expect(within(screen.getByRole("navigation", { name: "Site" })).getByRole("link", { name: "Meet the crew" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("contentinfo")).toHaveTextContent("© 2026 Little Homey");
  // Money Bags "knows what everything costs": furniture prices are fine, model-call costs are not.
  expect((heading.closest("main") as HTMLElement).textContent).not.toMatch(/\b(model|prompt|token)s?\b|\b(call|token|usage) costs?\b/i);
  expect(calls.map(([method, url]) => `${method} ${url}`).every((call) => call === "GET /auth/me")).toBe(true);
  await user.click(within(screen.getByRole("navigation", { name: "Site" })).getByRole("link", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("About in the top bar opens the About page for a visitor (About for a visitor)", async () => {
  const calls = signedOut();
  const user = userEvent.setup();
  show("/");
  const nav = await screen.findByRole("navigation", { name: "Site" });
  await user.click(within(nav).getByRole("link", { name: "About" }));
  const heading = await screen.findByRole("heading", { level: 1, name: "About Little Homey" });
  expect(within(screen.getByRole("navigation", { name: "Site" })).getByRole("link", { name: "About" })).toHaveAttribute("aria-current", "page");
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
  expect((heading.closest("article") as HTMLElement).textContent).not.toMatch(/\b(model name|prompt|token|frame|resolution|Eevee|Cycles)\b/i);
  expect(calls.map(([method, url]) => `${method} ${url}`).every((call) => call === "GET /auth/me")).toBe(true);
});

test("a signed-in owner at /crew gets the crew page under the owner's header (Signed-in owner at the crew page)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
  });
  show("/crew");
  expect(await screen.findByRole("heading", { level: 1, name: "Meet the crew" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Site" })).not.toBeInTheDocument();
});

test.each(["Site", "hero"])("Sign in from the %s opens the sign-in page, and signing in opens the Workspace (Sign in from the marketing page)", async (where) => {
  let signedIn = false;
  stubFetch((call) => {
    if (call === "GET /auth/me") return signedIn ? { body: { email: "owner@example.com" } } : { status: 401, body: { detail: "Not authenticated" } };
    if (call === "POST /auth/login") {
      signedIn = true;
      return { body: { email: "owner@example.com" } };
    }
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  const user = userEvent.setup();
  show("/");
  await screen.findByRole("heading", { level: 1, name: "Hello from Little Homey and his crew" });
  const links = screen.getAllByRole("link", { name: "Sign in" });
  expect(links).toHaveLength(2);
  const nav = screen.getByRole("navigation", { name: "Site" });
  const link = where === "Site" ? within(nav).getByRole("link", { name: "Sign in" }) : links.find((l) => !nav.contains(l))!;
  await user.click(link);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Email"), "owner@example.com");
  await user.type(screen.getByLabelText("Password"), "secret");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
});

test("the sign-in page's Little Homey link returns to the marketing page (Back from the sign-in page)", async () => {
  signedOut();
  show("/login");
  await screen.findByRole("heading", { name: "Sign in" });
  await userEvent.setup().click(screen.getByRole("link", { name: "Little Homey" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Hello from Little Homey and his crew" })).toBeInTheDocument();
});

test("a signed-in owner at / gets the Workspace (Signed-in owner at the root)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  show("/");
  expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("heading", { name: "Hello from Little Homey and his crew" })).not.toBeInTheDocument();
});

test.each(["/studio/pieces", "/somewhere-unknown"])("a signed-out visit to %s shows the sign-in page (Deep link while signed out)", async (path) => {
  signedOut();
  show(path);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Hello from Little Homey and his crew" })).not.toBeInTheDocument();
});
