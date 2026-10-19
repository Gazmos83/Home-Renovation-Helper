import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { DuplicateRoom } from "./DuplicateRoom";

function show(versions: number[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DuplicateRoom room="Wohnen" versions={versions} />
    </QueryClientProvider>,
  );
}

test("the form is prefilled with the latest layout and Duplicate sends the choice", async () => {
  const calls = stubFetch((call) =>
    call === "POST /rooms/Wohnen/duplicate"
      ? { status: 201, body: { room: "Wohnen (copy)", composition: { slug: "wohnen-copy", version: 1 } } }
      : undefined,
  );
  show([1, 2, 18]);
  await userEvent.click(screen.getByRole("button", { name: "Duplicate room" }));
  expect(screen.getByLabelText("Name of the copy")).toHaveValue("Wohnen (copy)");
  const layout = screen.getByLabelText("Layout to copy");
  expect(layout).toHaveValue("18");
  expect([...(layout as HTMLSelectElement).options].map((o) => o.text)).toEqual([
    "Version 18",
    "Version 2",
    "Version 1",
    "No layout",
  ]);
  await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  await vi.waitFor(() =>
    expect(calls.at(-1)).toEqual(["POST", "/rooms/Wohnen/duplicate", { name: "Wohnen (copy)", version: 18 }]),
  );
  await vi.waitFor(() => expect(screen.getByRole("button", { name: "Duplicate room" })).toBeInTheDocument());
});

test("No layout sends no version", async () => {
  const calls = stubFetch((call) =>
    call === "POST /rooms/Wohnen/duplicate" ? { status: 201, body: { room: "Wohnen B", composition: null } } : undefined,
  );
  show([1]);
  await userEvent.click(screen.getByRole("button", { name: "Duplicate room" }));
  await userEvent.selectOptions(screen.getByLabelText("Layout to copy"), "No layout");
  await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  await vi.waitFor(() =>
    expect(calls.at(-1)).toEqual(["POST", "/rooms/Wohnen/duplicate", { name: "Wohnen (copy)", version: null }]),
  );
});

test("a room without a composition has no layout choice", async () => {
  show([]);
  await userEvent.click(screen.getByRole("button", { name: "Duplicate room" }));
  expect(screen.queryByLabelText("Layout to copy")).not.toBeInTheDocument();
});

test("a refusal is shown and the form stays open", async () => {
  stubFetch((call) =>
    call === "POST /rooms/Wohnen/duplicate"
      ? { status: 409, body: { detail: { failure_class: "name_taken", reason: "a room is already named 'Küche'; choose another name" } } }
      : undefined,
  );
  show([]);
  await userEvent.click(screen.getByRole("button", { name: "Duplicate room" }));
  await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("a room is already named 'Küche'");
  expect(screen.getByRole("group", { name: "Duplicate room" })).toBeInTheDocument();
});
