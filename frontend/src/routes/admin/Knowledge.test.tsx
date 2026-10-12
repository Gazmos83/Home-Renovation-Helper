import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Knowledge from "./Knowledge";

const pending = { id: "test-version", key: "test", metadata: { title: "TEST board", edition: "1", source_url: null }, collections: ["material_datasheets"], state: "pending", rights_status: "pending_or_revoked", verification_status: "unverified", reviewed_by: null, grants: {}, rights: [], passages: 0, properties: [], local_path: null, content_hash: null, superseded_by: null };
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Knowledge /></QueryClientProvider>);
}

test("pending links are distinct from content, rights and technical review; grants do not trigger ingestion", async () => {
  let row = pending;
  const calls = stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [row] };
    if (call === "POST /admin/knowledge/test-version/rights") { row = { ...pending, rights_status: "approved", grants: { retention: {} } }; return { body: row }; }
  });
  show();
  expect(await screen.findByText("Link-only / pending")).toBeInTheDocument();
  expect(screen.getByText("Rights pending / revoked / expired")).toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Manage TEST board" }));
  expect(screen.getByRole("button", { name: "Stage PDF only" })).toBeDisabled();
  await user.type(screen.getByLabelText("Rights reviewer"), "fixture author");
  await user.clear(screen.getByLabelText("Supporting rights evidence"));
  await user.paste("Original fixture author permits local retention");
  await user.clear(screen.getByLabelText("Operation grants (JSON)"));
  await user.paste('{"retention": {"pages": null, "blocks": null}}');
  await user.click(screen.getByRole("button", { name: "Record approval" }));
  expect(await screen.findByText("Rights approved")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stage PDF only" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Run authorised ingestion" })).toBeDisabled();
  expect(screen.getByText("unverified")).toBeInTheDocument();
  expect(calls.some(([method, url]) => method === "POST" && url.endsWith("/ingest"))).toBe(false);
});

test("unsupported approvals display the server refusal; preview separates evidence from metadata", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [pending] };
    if (call === "POST /admin/knowledge/test-version/rights") return { status: 422, body: { detail: { reason: "approval needs documented operation grants" } } };
    if (call === "POST /admin/knowledge/search") return { body: { evidence: [], metadata_only: [{ title: "DIN fixture", source_url: "https://example.org/standard" }], limitation: "No eligible clauses" } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage TEST board" }));
  await user.type(screen.getByLabelText("Rights reviewer"), "fixture author");
  await user.clear(screen.getByLabelText("Supporting rights evidence"));
  await user.type(screen.getByLabelText("Supporting rights evidence"), "Purchased copy");
  await user.click(screen.getByRole("button", { name: "Record approval" }));
  const refusal = await screen.findByRole("alert");
  expect(refusal).toHaveTextContent("documented operation grants");
  expect(refusal.parentElement).toContainElement(screen.getByRole("button", { name: "Record approval" }));
  await user.type(screen.getByLabelText("Engineering query"), "DIN fixture");
  await user.selectOptions(screen.getByLabelText("Search mode"), "keyword");
  await user.click(screen.getByRole("button", { name: "Preview eligible evidence" }));
  expect(await screen.findByText("Eligible evidence (0)")).toBeInTheDocument();
  expect(screen.getByText("Metadata only (1)")).toBeInTheDocument();
});

test("choosing Manage moves focus to the selected source panel", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [pending] };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage TEST board" }));
  expect(screen.getByRole("heading", { name: "TEST board" })).toHaveFocus();
});

const linked = { ...pending, metadata: { ...pending.metadata, source_url: "https://example.org/a.pdf", license_status: "pending" } };

test("a preset fills grants only on selection and the draft note must be edited before approval is recorded", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [linked] };
    if (call === "POST /admin/knowledge/test-version/rights") return { body: linked };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage TEST board" }));
  expect(screen.getByLabelText("Local use: extraction, local_embedding, local_retrieval, retention")).not.toBeChecked();
  expect(screen.getByLabelText("Operation grants (JSON)")).toHaveValue("{}");
  expect((screen.getByLabelText("Supporting rights evidence") as HTMLTextAreaElement).value).toContain("https://example.org/a.pdf");
  await user.type(screen.getByLabelText("Rights reviewer"), "fixture author");
  expect(screen.getByRole("button", { name: "Record approval" })).toBeDisabled();
  await user.click(screen.getByLabelText("Local use: extraction, local_embedding, local_retrieval, retention"));
  expect((screen.getByLabelText("Operation grants (JSON)") as HTMLTextAreaElement).value).toContain("local_embedding");
  expect((screen.getByLabelText("Operation grants (JSON)") as HTMLTextAreaElement).value).not.toContain("remote_model_use");
  expect(screen.getByRole("button", { name: "Record approval" })).toBeDisabled();
  await user.clear(screen.getByLabelText("Supporting rights evidence"));
  await user.paste("Federal publication; no copyright notice on the title pages");
  expect(calls.some(([method, url]) => method === "POST" && url.endsWith("/rights"))).toBe(false);
  await user.click(screen.getByRole("button", { name: "Record approval" }));
  const sent = calls.find(([method, url]) => method === "POST" && url.endsWith("/rights"));
  expect(sent).toBeTruthy();
});

test("catalogue entries register on request and the technical reviewer defaults to the rights reviewer", async () => {
  let registered = false;
  const calls = stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: registered ? [] : [{ key: "usda", metadata: { title: "USDA handbook", edition: "2021" } }] };
    if (call === "GET /admin/knowledge") return { body: registered ? [linked] : [] };
    if (call === "POST /admin/knowledge/catalogue/usda/register") { registered = true; return { status: 201, body: linked }; }
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByText(/Catalogue entries not yet registered/));
  await user.click(screen.getByRole("button", { name: "Register usda" }));
  expect(await screen.findByText("Registered metadata only. No content downloaded or indexed.")).toBeInTheDocument();
  expect(calls.some(([method, url]) => method === "POST" && url.endsWith("/rights"))).toBe(false);
  expect(screen.getByRole("button", { name: "Ingest from official link" })).toBeDisabled();
  await user.type(screen.getByLabelText("Rights reviewer"), "fixture author");
  expect(screen.getByLabelText("Technical reviewer")).toHaveValue("fixture author");
});

test("staging errors show beside the Stage PDF only button", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [{ ...pending, grants: { retention: {} } }] };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage TEST board" }));
  await user.click(screen.getByRole("button", { name: "Stage PDF only" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Choose a PDF.");
  expect(alert.parentElement).toContainElement(screen.getByRole("button", { name: "Stage PDF only" }));
  expect(alert.parentElement).not.toHaveClass("sticky");
});

test("ingestion errors show beside the ingestion buttons", async () => {
  const withGrants = { ...linked, grants: Object.fromEntries(["extraction", "local_embedding", "local_retrieval", "retention"].map((name) => [name, {}])) };
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [withGrants] };
    if (call === "POST /admin/knowledge/test-version/ingest-link") return { body: { state: "failed", blocks: 0, reason: "host robots rules refuse this service" } };
    if (call === "POST /admin/knowledge/test-version/ingest") return { body: { state: "failed", blocks: 0, reason: "no authorised blocks to publish" } };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage TEST board" }));
  const button = screen.getByRole("button", { name: "Ingest from official link" });
  await user.click(button);
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("robots rules refuse");
  expect(alert.parentElement).toContainElement(button);
  expect(alert.parentElement).not.toHaveClass("sticky");
  const authorised = screen.getByRole("button", { name: "Run authorised ingestion" });
  await user.click(authorised);
  const second = await screen.findByText(/Ingestion failed: no authorised blocks/);
  expect(second.parentElement).toContainElement(authorised);
  expect(second.parentElement).not.toHaveClass("sticky");
});

test("sources are listed ten per page", async () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ ...pending, id: `v${index}`, metadata: { ...pending.metadata, title: `Source ${String(index).padStart(2, "0")}` } }));
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: rows };
  });
  show();
  const user = userEvent.setup();
  expect(await screen.findByText("Page 1 of 2 (12 sources)")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /^Manage Source/ })).toHaveLength(10);
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Next page" }));
  expect(screen.getAllByRole("button", { name: /^Manage Source/ })).toHaveLength(2);
  expect(screen.getByText("Page 2 of 2 (12 sources)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
});

test("the source list can be filtered by approval or verification and sorted alphabetically", async () => {
  const rows = [
    { ...pending, id: "a", metadata: { ...pending.metadata, title: "Zeta board" }, rights_status: "approved" },
    { ...pending, id: "b", metadata: { ...pending.metadata, title: "Alpha board" }, verification_status: "verified" },
    { ...pending, id: "c", metadata: { ...pending.metadata, title: "Mid board" } },
  ];
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: rows };
  });
  show();
  const user = userEvent.setup();
  const names = () => screen.getAllByRole("button", { name: /^Manage / }).map((button) => button.textContent);
  await screen.findByRole("button", { name: "Manage Zeta board" });
  expect(names()).toEqual(["Manage Zeta board", "Manage Alpha board", "Manage Mid board"]);
  await user.click(screen.getByRole("button", { name: "All, A–Z" }));
  expect(names()).toEqual(["Manage Alpha board", "Manage Mid board", "Manage Zeta board"]);
  await user.click(screen.getByRole("button", { name: "Approved only" }));
  expect(names()).toEqual(["Manage Zeta board"]);
  await user.click(screen.getByRole("button", { name: "Verified only" }));
  expect(screen.getByRole("button", { name: "Verified only" })).toHaveAttribute("aria-pressed", "true");
  expect(names()).toEqual(["Manage Alpha board"]);
});

test("Insert template fills the registration form with every registrable field and no approval fields", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [] };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByText("Register a source version"));
  const field = screen.getByLabelText("Source metadata and collections (JSON)") as HTMLTextAreaElement;
  await user.clear(field);
  await user.click(screen.getByRole("button", { name: "Insert template" }));
  const template = JSON.parse(field.value);
  expect(Object.keys(template.metadata)).toEqual(expect.arrayContaining(["title", "publisher", "source_url", "edition", "jurisdiction", "language", "license_status", "manufacturer", "part_number"]));
  expect(template.metadata).not.toHaveProperty("verification_status");
  expect(template.metadata).not.toHaveProperty("approved_for_embedding");
});

const readBlob = (blob: Blob) => new Promise<string>((resolve) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
test("Export template downloads the registration template as a file", async () => {
  const saved: Blob[] = [];
  const names: string[] = [];
  URL.createObjectURL = (blob: Blob | MediaSource) => { saved.push(blob as Blob); return "blob:test"; };
  URL.revokeObjectURL = () => undefined;
  HTMLAnchorElement.prototype.click = function (this: HTMLAnchorElement) { names.push(this.download); };
  stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [] };
    if (call === "GET /admin/knowledge/catalogue") return { body: [] };
    if (call === "GET /admin/knowledge") return { body: [] };
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByText("Register a source version"));
  await user.click(screen.getByRole("button", { name: "Export template" }));
  expect(names).toEqual(["engineering-source-template.json"]);
  const template = JSON.parse(await readBlob(saved[0]));
  expect(template.metadata).toHaveProperty("source_url", null);
  expect(template.metadata).not.toHaveProperty("approved_for_embedding");
});
