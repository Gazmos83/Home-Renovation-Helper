import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import EngineeringMethods from "./EngineeringMethods";

test("unreviewed methods cannot be enabled; a disable decision preserves method visibility", async () => {
  const method = { id: "shelf_immediate", version: "1", domain: "Rectangular reviewed shelf case only", enabled: false, releasable: false, implemented: false, qualified_review_state: "pending", definition_hash: "a".repeat(64), units: ["m", "N"], required_inputs: ["supports"], citation_evidence_ids: [], criteria: [], independent_reference_cases: [], limitation: "Exact equations and qualified review pending" };
  const calls = stubFetch((call) => {
    if (call === "GET /admin/engineering-methods") return { body: [method] };
    if (call === "POST /admin/engineering-methods/shelf_immediate/review") return { body: { enabled: false } };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EngineeringMethods /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "shelf_immediate · unavailable" }));
  expect(screen.getByRole("button", { name: "Accept qualified review and enable" })).toBeDisabled();
  await user.click(screen.getByLabelText("Method reviewer")); await user.paste("fixture developer");
  await user.click(screen.getByLabelText("Qualified-review evidence")); await user.paste("No qualification asserted; disabling only");
  await user.click(screen.getByLabelText("Scope, criteria and reference review evidence")); await user.paste("Keep unreviewed method disabled");
  await user.click(screen.getByRole("button", { name: "Disable method, retain history" }));
  expect(calls.some(([method, url]) => method === "POST" && url.includes("shelf_immediate/review"))).toBe(true);
});

const readBlob = (blob: Blob) => new Promise<string>((resolve) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
test("template exports download a reviewer worksheet without sending anything to the server", async () => {
  const saved: Blob[] = [];
  const names: string[] = [];
  URL.createObjectURL = (blob: Blob | MediaSource) => { saved.push(blob as Blob); return "blob:test"; };
  URL.revokeObjectURL = () => undefined;
  HTMLAnchorElement.prototype.click = function (this: HTMLAnchorElement) { names.push(this.download); };
  const method = { id: "shelf_immediate", version: "1", domain: "Rectangular shelf", units: ["m"], required_inputs: ["span"], citation_evidence_ids: [], criteria: [], independent_reference_cases: [], definition_hash: "abc", enabled: false, releasable: false, implemented: false, qualified_review_state: "pending", limitation: null };
  const calls = stubFetch((call) => { if (call === "GET /admin/engineering-methods") return { body: [method] }; });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EngineeringMethods /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Export blank method template" }));
  await user.click(screen.getByRole("button", { name: "shelf_immediate · unavailable" }));
  await user.click(screen.getByRole("button", { name: "Export method package" }));
  expect(names).toEqual(["engineering-method-template.json", "shelf_immediate-v1-review-package.json"]);
  const blank = JSON.parse(await readBlob(saved[0]));
  const filled = JSON.parse(await readBlob(saved[1]));
  expect(blank.method_id).toBe("");
  expect(blank.qualified_review).toEqual({ reviewer: "", qualification_evidence: "", scope_evidence: "" });
  expect(filled.method_id).toBe("shelf_immediate");
  expect(filled.definition_hash).toBe("abc");
  expect(calls.filter(([verb]) => verb !== "GET")).toEqual([]);
});

const sheetMethod = { id: "shelf_immediate", version: "1", domain: "Rectangular shelf", units: ["m"], required_inputs: ["span"], citation_evidence_ids: [], criteria: [], independent_reference_cases: [], definition_hash: "a".repeat(64), enabled: false, releasable: false, implemented: false, qualified_review_state: "pending", limitation: null };
async function openMethod() {
  const calls = stubFetch((call) => { if (call === "GET /admin/engineering-methods") return { body: [sheetMethod] }; });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EngineeringMethods /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "shelf_immediate · unavailable" }));
  return { user, calls };
}
const sheetFile = (sheet: unknown) => new File([JSON.stringify(sheet)], "worksheet.json", { type: "application/json" });

test("importing a worksheet fills the review form but records nothing", async () => {
  const { user, calls } = await openMethod();
  await user.upload(screen.getByLabelText("Method worksheet file"), sheetFile({ method_id: "shelf_immediate", method_version: "1", definition_hash: "a".repeat(64), supported_domain_limits: "simple supports only", citations: [{ evidence_id: "e1" }], criteria: [], independent_reference_cases: [], qualified_review: { reviewer: "Fixture reviewer", qualification_evidence: "Fixture qualification", scope_evidence: "Scope checked" } }));
  expect(await screen.findByText(/Nothing has been recorded/)).toBeInTheDocument();
  expect(screen.getByLabelText("Method reviewer")).toHaveValue("Fixture reviewer");
  expect(screen.getByLabelText("Qualified-review evidence")).toHaveValue("Fixture qualification");
  expect((screen.getByLabelText("Scope, criteria and reference review evidence") as HTMLTextAreaElement).value).toContain("simple supports only");
  expect(screen.getByRole("button", { name: "Accept qualified review and enable" })).toBeDisabled();
  expect(calls.filter(([verb]) => verb !== "GET")).toEqual([]);
});

test("a worksheet for another method or an older definition is refused beside the Import button", async () => {
  const { user } = await openMethod();
  await user.upload(screen.getByLabelText("Method worksheet file"), sheetFile({ method_id: "joint_x", method_version: "1" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not shelf_immediate v1");
  await user.upload(screen.getByLabelText("Method worksheet file"), sheetFile({ method_id: "shelf_immediate", method_version: "1", definition_hash: "b".repeat(64) }));
  expect(await screen.findByText(/different version of this method definition/)).toBeInTheDocument();
  await user.upload(screen.getByLabelText("Method worksheet file"), sheetFile({ method_id: "shelf_immediate", method_version: "1", qualified_review: { scope_evidence: "x".repeat(4100) } }));
  expect(await screen.findByText(/longer than the 4000-character review limit/)).toBeInTheDocument();
  expect(screen.getByLabelText("Method reviewer")).toHaveValue("");
  expect(screen.getByRole("alert").parentElement).toContainElement(screen.getByRole("button", { name: "Import worksheet" }));
});
