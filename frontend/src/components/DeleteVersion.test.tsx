import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { DeleteVersion } from "./DeleteVersion";

function show(only = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onDeleted = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <DeleteVersion packageId="bench" version={2} only={only} onDeleted={onDeleted} />
    </QueryClientProvider>,
  );
  return onDeleted;
}

test("pressing delete only asks; yes sends the delete", async () => {
  const calls = stubFetch((call) => (call === "DELETE /packages/bench/versions/2" ? { status: 204 } : undefined));
  const onDeleted = show();
  await userEvent.click(screen.getByRole("button", { name: "Delete version 2" }));
  expect(calls).toEqual([]);
  expect(
    screen.getByText("Are you sure? Version 2 and its renders, reviews and pricings will be deleted. This cannot be undone."),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Yes, delete version 2" }));
  await vi.waitFor(() => expect(onDeleted).toHaveBeenCalled());
  expect(calls).toEqual([["DELETE", "/packages/bench/versions/2", undefined]]);
});

test("cancel deletes nothing and shows the control again", async () => {
  const calls = stubFetch(() => undefined);
  const onDeleted = show();
  await userEvent.click(screen.getByRole("button", { name: "Delete version 2" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Delete version 2" })).toBeInTheDocument();
  expect(screen.queryByText(/Are you sure/)).not.toBeInTheDocument();
  expect(calls).toEqual([]);
  expect(onDeleted).not.toHaveBeenCalled();
});

test("the only version's question says the whole piece goes", async () => {
  stubFetch(() => undefined);
  show(true);
  await userEvent.click(screen.getByRole("button", { name: "Delete version 2" }));
  expect(screen.getByText(/the whole piece will be deleted/)).toBeInTheDocument();
});

test("a refusal is shown with its reason next to the control", async () => {
  const reason = "bench version 2 is placed in the room composition Living room version 3; it cannot be deleted while it is placed";
  stubFetch((call) =>
    call === "DELETE /packages/bench/versions/2"
      ? { status: 409, body: { detail: { failure_class: "version_in_use", reason } } }
      : undefined,
  );
  const onDeleted = show();
  await userEvent.click(screen.getByRole("button", { name: "Delete version 2" }));
  await userEvent.click(screen.getByRole("button", { name: "Yes, delete version 2" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Living room version 3");
  expect(onDeleted).not.toHaveBeenCalled();
});
