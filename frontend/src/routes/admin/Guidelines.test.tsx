import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Guidelines from "./Guidelines";

const listed = {
  id: "topnotch-shelf-brackets", origin: "list", title: "How Many Brackets", jurisdiction: "UK",
  published_on: "2026-07-24", licence: "retailer", format: "pdf", passages: 4, deletable: false,
};
const uploaded = {
  id: "upload-abc123def456", origin: "upload", title: "ASR A1.2", jurisdiction: "Germany",
  published_on: "2022-01-01", licence: "BAuA", format: "pdf", passages: 12, deletable: true,
  size_bytes: 2048, ingested_at: "2026-10-10T08:00:00Z", error: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Guidelines />
    </QueryClientProvider>,
  );
}

test("sources are listed, a PDF is uploaded with its details, and only an upload can be deleted", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /admin/guidelines") return { body: [listed, uploaded] };
    if (call === "POST /admin/guidelines") return { status: 201, body: uploaded };
    if (call === "DELETE /admin/guidelines/upload-abc123def456") return { status: 204 };
  });
  show();
  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(within(rows[0]).queryByRole("button", { name: "Delete" })).toBeNull();
  expect(within(rows[1]).getByRole("button", { name: "Delete" })).toBeInTheDocument();

  const user = userEvent.setup();
  await user.upload(screen.getByLabelText("PDF"), new File(["%PDF-1.4"], "asr.pdf", { type: "application/pdf" }));
  await user.type(screen.getByLabelText("Title"), "ASR A1.2");
  await user.type(screen.getByLabelText("Jurisdiction"), "Germany");
  await user.type(screen.getByLabelText("Published on"), "2022-01-01");
  await user.type(screen.getByLabelText("Licence note"), "BAuA");
  await user.click(screen.getByRole("button", { name: "Upload and ingest" }));
  const post = calls.find(([method, url]) => method === "POST" && url === "/admin/guidelines");
  const form = post ? (post[2] as FormData) : null;
  expect(form).toBeInstanceOf(FormData);
  expect(form?.get("title")).toBe("ASR A1.2");

  await user.click(within(rows[1]).getByRole("button", { name: "Delete" }));
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("DELETE /admin/guidelines/upload-abc123def456");
});

test("a refused upload shows the reason", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/guidelines") return { body: [] };
    if (call === "POST /admin/guidelines")
      return { status: 422, body: { detail: { failure_class: "upload_refused", field: "file", reason: "the file is not a PDF" } } };
  });
  show();
  const user = userEvent.setup();
  await user.upload(screen.getByLabelText("PDF"), new File(["png"], "x.pdf", { type: "application/pdf" }));
  await user.type(screen.getByLabelText("Title"), "x");
  await user.type(screen.getByLabelText("Jurisdiction"), "x");
  await user.type(screen.getByLabelText("Published on"), "2022-01-01");
  await user.type(screen.getByLabelText("Licence note"), "x");
  await user.click(screen.getByRole("button", { name: "Upload and ingest" }));
  expect(await screen.findByText(/the file is not a PDF/)).toBeInTheDocument();
});
