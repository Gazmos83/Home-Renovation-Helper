import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { DuplicatePiece, idFromName } from "./DuplicatePiece";

const SUMMARY = {
  package_id: "sideboard-1200",
  name: "Sideboard",
  versions: [3, 2, 1],
  approved: [],
  conversations: [],
  refusal: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onDuplicated = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <DuplicatePiece packageId="sideboard-1200" versions={[3, 2, 1]} onDuplicated={onDuplicated} />
    </QueryClientProvider>,
  );
  return onDuplicated;
}

test("a name is made into an id as the service does", () => {
  expect(idFromName("Sideboard (copy)")).toBe("sideboard-copy");
  expect(idFromName("  Hall -- Bench ")).toBe("hall-bench");
});

test("the form is prefilled and Duplicate sends the chosen version, name and id", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /packages/sideboard-1200/deletion") return { body: SUMMARY };
    if (call === "POST /packages/sideboard-1200/duplicate")
      return { status: 202, body: { package_id: "sideboard-hall", version: 1, status: "queued", thread_id: "t-9" } };
  });
  const onDuplicated = show();
  await userEvent.click(screen.getByRole("button", { name: "Duplicate piece" }));
  const name = screen.getByLabelText("Name of the copy");
  await vi.waitFor(() => expect(name).toHaveValue("Sideboard (copy)"));
  expect(screen.getByLabelText("Id of the copy")).toHaveValue("sideboard-copy");
  expect(screen.getByLabelText("Version to copy")).toHaveValue("3");
  await userEvent.selectOptions(screen.getByLabelText("Version to copy"), "1");
  await userEvent.clear(name);
  await userEvent.type(name, "Sideboard Hall");
  expect(screen.getByLabelText("Id of the copy")).toHaveValue("sideboard-hall");
  await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  await vi.waitFor(() => expect(onDuplicated).toHaveBeenCalledWith("t-9"));
  expect(calls.at(-1)).toEqual([
    "POST",
    "/packages/sideboard-1200/duplicate",
    { version: 1, name: "Sideboard Hall", package_id: "sideboard-hall" },
  ]);
});

test("a refusal is shown and the form stays open", async () => {
  stubFetch((call) => {
    if (call === "GET /packages/sideboard-1200/deletion") return { body: SUMMARY };
    if (call === "POST /packages/sideboard-1200/duplicate")
      return {
        status: 409,
        body: { detail: { failure_class: "package_exists", reason: "the package id 'sideboard-copy' is already in use; choose another id" } },
      };
  });
  const onDuplicated = show();
  await userEvent.click(screen.getByRole("button", { name: "Duplicate piece" }));
  await vi.waitFor(() => expect(screen.getByLabelText("Name of the copy")).toHaveValue("Sideboard (copy)"));
  await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("'sideboard-copy' is already in use");
  expect(screen.getByRole("group", { name: "Duplicate piece" })).toBeInTheDocument();
  expect(onDuplicated).not.toHaveBeenCalled();
});

test("Cancel sends nothing", async () => {
  const calls = stubFetch((call) => (call === "GET /packages/sideboard-1200/deletion" ? { body: SUMMARY } : undefined));
  show();
  await userEvent.click(screen.getByRole("button", { name: "Duplicate piece" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(calls.some(([m]) => m === "POST")).toBe(false);
  expect(screen.getByRole("button", { name: "Duplicate piece" })).toBeInTheDocument();
});
