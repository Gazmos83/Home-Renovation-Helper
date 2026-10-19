import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import path from "node:path";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import App from "../App";
import { stubFetch } from "../test/fetchStub";

/** little-homey-brand-about-footer: the name, the About page and the footer. */

function show(pathname: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[pathname]}><App /></MemoryRouter>
    </QueryClientProvider>,
  );
}

function signedIn() {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /help") return { body: { topics: [] } };
  });
}

test("About opens from the header and explains the app in plain words (About from the header)", async () => {
  signedIn();
  show("/help");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  await userEvent.setup().click(within(nav).getByRole("link", { name: "About" }));
  const heading = await screen.findByRole("heading", { level: 1, name: "About Little Homey" });
  const page = heading.closest("article") as HTMLElement;
  expect(page).toHaveTextContent("ordinary laptop");
  expect(page).toHaveTextContent("The magic is in the revision");
  expect(page).toHaveTextContent("download it and add it to a 3D model of your home");
  expect(page.textContent).not.toMatch(/\b(model name|prompt|token|frame|resolution|Eevee|Cycles)\b/i);
});

test("the last section says pictures keep the piece's measurements (Measurements stay put)", async () => {
  signedIn();
  show("/about");
  const heading = await screen.findByRole("heading", { level: 1, name: "About Little Homey" });
  const page = heading.closest("article") as HTMLElement;
  const sections = within(page).getAllByRole("heading", { level: 2 });
  expect(sections.at(-1)).toHaveTextContent("Your measurements stay put");
  expect(page).toHaveTextContent("Every piece is built from its exact measurements");
  expect(page).toHaveTextContent("A change happens only when you ask for it");
});

test("About no longer lists the crew; the crew has its own page (Crew moved to its own page)", async () => {
  signedIn();
  show("/about");
  await screen.findByRole("heading", { level: 1, name: "About Little Homey" });
  expect(screen.queryByRole("heading", { name: "Meet the crew" })).not.toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "The crew" })).not.toBeInTheDocument();
});

test("the header links are the name, Help and About, then Sign out (Header links)", async () => {
  signedIn();
  show("/about");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Little Homey", "Help", "About"]);
  expect(within(nav).getByRole("link", { name: "Little Homey" })).toHaveAttribute("href", "/studio/workspace");
  expect(within(nav).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});

test("About signed out shows the About page under the visitor's top bar (Signed out)", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/about");
  expect(await screen.findByRole("heading", { level: 1, name: "About Little Homey" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Site" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
});

test("the footer shows the name, year, version and build, and About when signed in (Footer on the Workspace)", async () => {
  signedIn();
  show("/about");
  const footer = await screen.findByRole("contentinfo");
  expect(footer).toHaveTextContent("© 2026 Little Homey");
  expect(footer).toHaveTextContent("v0.0.0 · test");
  expect(within(footer).getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
});

test("the sign-in page's footer has no About link (Footer on the sign-in page)", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/login");
  const footer = await screen.findByRole("contentinfo");
  expect(footer).toHaveTextContent("© 2026 Little Homey");
  expect(within(footer).queryByRole("link")).not.toBeInTheDocument();
});

test("the tab is titled Little Homey with the house icon (Tab title and icon)", () => {
  const html = readFileSync(path.resolve(__dirname, "../../index.html"), "utf-8");
  expect(html).toContain("<title>Little Homey</title>");
  expect(html).toContain('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />');
  expect(readFileSync(path.resolve(__dirname, "../../public/favicon.svg"), "utf-8")).toContain("<svg");
});
