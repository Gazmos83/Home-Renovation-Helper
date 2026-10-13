import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { PieceVariants, RoomVariants, Variants, keepLookRequest } from "./Variants";
import type { Variant } from "../lib/api";

const walnut: Variant = {
  id: "walnut-draft",
  label: "Walnut",
  tier: "draft",
  note: "appearance only, not a priced material",
  looks: { carcass: "walnut" },
  style: null,
  created_at: "2026-10-12T10:00:00+00:00",
  still: "/packages/bench/versions/1/files/variants/walnut-draft/still.png",
};

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

test("each picture shows its label, tier and the appearance note", () => {
  render(<Variants items={[walnut]} />);
  expect(screen.getByRole("img", { name: "Walnut restyle" })).toHaveAttribute("src", walnut.still);
  expect(screen.getByText("draft")).toBeInTheDocument();
  expect(screen.getByText("appearance only, not a priced material")).toBeInTheDocument();
});

test("nothing shows while a version has no variants", () => {
  const { container } = render(<Variants items={[]} />);
  expect(container).toBeEmptyDOMElement();
});

test("no developer fields reach the page", () => {
  render(<Variants items={[walnut]} />);
  expect(screen.queryByText(/model|prompt|token|cost/i)).not.toBeInTheDocument();
});

test("a piece variant offers Use this look, which hands over the request; a room variant does not", async () => {
  const onUse = vi.fn();
  render(<Variants items={[walnut]} onUse={onUse} />);
  await userEvent.click(screen.getByRole("button", { name: "Use this look" }));
  expect(onUse).toHaveBeenCalledWith(walnut);
  const room: Variant = { ...walnut, id: "japandi-draft", label: "Japandi", looks: null, style: "japandi" };
  render(<Variants items={[room]} onUse={onUse} />);
  expect(screen.getAllByRole("button", { name: "Use this look" })).toHaveLength(1);
});

test("the request names the slot and look and asks about the real material before changing anything", () => {
  const text = keepLookRequest("bench", 1, walnut);
  expect(text).toContain("carcass as walnut");
  expect(text).toContain("bench version 1");
  expect(text).toContain("which real material");
});

test("a piece's variants are fetched from its version", async () => {
  stubFetch((call) => {
    if (call === "GET /packages/bench/versions/1/variants") return { body: [walnut] };
  });
  wrap(<PieceVariants packageId="bench" version={1} />);
  expect(await screen.findByRole("img", { name: "Walnut restyle" })).toBeInTheDocument();
});

test("a room's variants are fetched from its composition version", async () => {
  const room: Variant = { ...walnut, id: "japandi-draft", label: "Japandi", looks: null, style: "japandi" };
  stubFetch((call) => {
    if (call === "GET /compositions/wohnen/versions/2/variants") return { body: [room] };
  });
  wrap(<RoomVariants slug="wohnen" version={2} />);
  expect(await screen.findByRole("img", { name: "Japandi restyle" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Use this look" })).not.toBeInTheDocument();
});
