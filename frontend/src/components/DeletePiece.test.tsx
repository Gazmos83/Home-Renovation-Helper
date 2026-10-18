import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { DeletePiece } from "./DeletePiece";

const SUMMARY = {
  package_id: "sideboard-1200",
  name: "Sideboard",
  versions: [1, 2],
  approved: [{ version: 1, priced: true }],
  conversations: ["t-1"],
  refusal: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onDeleted = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <DeletePiece packageId="sideboard-1200" onDeleted={onDeleted} />
    </QueryClientProvider>,
  );
  return onDeleted;
}

test("pressing Delete piece only asks, listing what goes; yes sends the delete", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /packages/sideboard-1200/deletion") return { body: SUMMARY };
    if (call === "DELETE /packages/sideboard-1200") return { status: 204 };
  });
  const onDeleted = show();
  expect(calls).toEqual([]);
  await userEvent.click(screen.getByRole("button", { name: "Delete piece" }));
  expect(
    await screen.findByText(
      "Are you sure? Sideboard and all its 2 versions will be deleted with their renders, reviews and pricings.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("Approved: version 1, priced")).toBeInTheDocument();
  expect(screen.getByText("Its 1 conversation will be deleted too.")).toBeInTheDocument();
  expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
  expect(calls.some(([m]) => m === "DELETE")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Yes, delete Sideboard" }));
  await vi.waitFor(() => expect(onDeleted).toHaveBeenCalled());
  expect(calls.at(-1)).toEqual(["DELETE", "/packages/sideboard-1200", undefined]);
});

test("an unpriced approval and several conversations are worded so", async () => {
  stubFetch((call) =>
    call === "GET /packages/sideboard-1200/deletion"
      ? { body: { ...SUMMARY, approved: [{ version: 2, priced: false }], conversations: ["a", "b"] } }
      : undefined,
  );
  show();
  await userEvent.click(screen.getByRole("button", { name: "Delete piece" }));
  expect(await screen.findByText("Approved: version 2, not priced")).toBeInTheDocument();
  expect(screen.getByText("Its 2 conversations will be deleted too.")).toBeInTheDocument();
});

test("cancel deletes nothing and shows Delete piece again", async () => {
  const calls = stubFetch((call) => (call === "GET /packages/sideboard-1200/deletion" ? { body: SUMMARY } : undefined));
  const onDeleted = show();
  await userEvent.click(screen.getByRole("button", { name: "Delete piece" }));
  await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Delete piece" })).toBeInTheDocument();
  expect(calls.some(([m]) => m === "DELETE")).toBe(false);
  expect(onDeleted).not.toHaveBeenCalled();
});

test("a refusal is shown instead of the Yes button", async () => {
  const refusal = "sideboard-1200 version 1 is placed in the room composition Living room version 3; remove it from the composition first";
  stubFetch((call) =>
    call === "GET /packages/sideboard-1200/deletion" ? { body: { ...SUMMARY, refusal } } : undefined,
  );
  show();
  await userEvent.click(screen.getByRole("button", { name: "Delete piece" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Living room version 3");
  expect(screen.queryByRole("button", { name: /^Yes/ })).not.toBeInTheDocument();
});

test("a refusal from the delete itself is shown next to the control", async () => {
  stubFetch((call) => {
    if (call === "GET /packages/sideboard-1200/deletion") return { body: SUMMARY };
    if (call === "DELETE /packages/sideboard-1200") {
      return { status: 409, body: { detail: { failure_class: "turn_running", reason: "a reply is still being written" } } };
    }
  });
  const onDeleted = show();
  await userEvent.click(screen.getByRole("button", { name: "Delete piece" }));
  await userEvent.click(await screen.findByRole("button", { name: "Yes, delete Sideboard" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("a reply is still being written");
  expect(onDeleted).not.toHaveBeenCalled();
});
