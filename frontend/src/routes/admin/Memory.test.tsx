import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Memory from "./Memory";

const defaults = {
  recent_inputs: 5, trigger_percent: 100, keep_turns: 0, note_tokens: 400, note_instructions: "You keep the notes.", tool_result_chars: 300,
  reviews: "auto", save_preferences: true, other_builds: "line", include_preferences: true,
  include_review_items: true, include_version_verdicts: true, render_ratings: 5, include_extension_requests: true,
};
const payload = { settings: { ...defaults, keep_turns: 3 }, defaults, fixed_rules: ["Generator-extension requests are always saved."] };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Memory />
    </QueryClientProvider>,
  );
}

test("settings show their defaults, a change is saved, a changed one resets, and the fixed rules are listed", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /admin/memory") return { body: payload };
    if (call === "PUT /admin/memory") return { body: { ...payload, settings: { ...payload.settings, trigger_percent: 75 } } };
    if (call === "DELETE /admin/memory/keep_turns") return { body: { ...payload, settings: defaults } };
  });
  show();
  const user = userEvent.setup();
  const trigger = await screen.findByLabelText(/Start compressing at/);
  expect(screen.getByText("Generator-extension requests are always saved.")).toBeInTheDocument();
  await user.clear(trigger);
  await user.type(trigger, "75");
  await user.click(screen.getAllByRole("button", { name: "Save" })[0]);
  expect(calls).toContainEqual(["PUT", "/admin/memory", { trigger_percent: 75 }]);
  await user.click(screen.getByRole("button", { name: "Reset Recent turns always kept in full" }));
  expect(calls.map(([m, u]) => `${m} ${u}`)).toContain("DELETE /admin/memory/keep_turns");
});

test("an out-of-range value shows the refusal", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/memory") return { body: { settings: defaults, defaults, fixed_rules: [] } };
    if (call === "PUT /admin/memory")
      return { status: 422, body: { detail: { failure_class: "invalid_setting", field: "keep_turns", reason: "Input should be less than or equal to 20" } } };
  });
  show();
  const user = userEvent.setup();
  const kept = await screen.findByLabelText("Recent turns always kept in full");
  await user.clear(kept);
  await user.type(kept, "50");
  await user.click(screen.getAllByRole("button", { name: "Save" })[1]);
  expect(await screen.findByText(/less than or equal to 20/)).toBeInTheDocument();
});

test("recent inputs show the default of 5, save, reset and show a refusal", async () => {
  let current = 5;
  const calls = stubFetch((call, init) => {
    if (call === "GET /admin/memory") return { body: { settings: { ...defaults, recent_inputs: current }, defaults, fixed_rules: [] } };
    if (call === "PUT /admin/memory") {
      const sent = JSON.parse(String(init?.body)).recent_inputs;
      if (sent > 20) {
        return { status: 422, body: { detail: { failure_class: "invalid_setting", field: "recent_inputs", reason: "Input should be less than or equal to 20" } } };
      }
      current = sent;
      return { body: { settings: { ...defaults, recent_inputs: current }, defaults, fixed_rules: [] } };
    }
    if (call === "DELETE /admin/memory/recent_inputs") {
      current = 5;
      return { body: { settings: defaults, defaults, fixed_rules: [] } };
    }
  });
  show();
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Recent inputs sent in full (0 = the trigger decides)");
  expect(field).toHaveValue(5);
  await user.clear(field);
  await user.type(field, "8");
  await user.click(screen.getAllByRole("button", { name: "Save" })[2]);
  expect(calls).toContainEqual(["PUT", "/admin/memory", { recent_inputs: 8 }]);
  await user.click(await screen.findByRole("button", { name: "Reset Recent inputs sent in full (0 = the trigger decides)" }));
  expect(calls.map(([m, u]) => `${m} ${u}`)).toContain("DELETE /admin/memory/recent_inputs");
  const again = await screen.findByLabelText("Recent inputs sent in full (0 = the trigger decides)");
  await user.clear(again);
  await user.type(again, "21");
  await user.click(screen.getAllByRole("button", { name: "Save" })[2]);
  expect(await screen.findByText(/less than or equal to 20/)).toBeInTheDocument();
});

test("open version verdicts can be left out and reset", async () => {
  let current = true;
  const calls = stubFetch((call, init) => {
    const body = () => ({ settings: { ...defaults, include_version_verdicts: current }, defaults, fixed_rules: [] });
    if (call === "GET /admin/memory") return { body: body() };
    if (call === "PUT /admin/memory") {
      current = JSON.parse(String(init?.body)).include_version_verdicts;
      return { body: body() };
    }
    if (call === "DELETE /admin/memory/include_version_verdicts") {
      current = true;
      return { body: body() };
    }
  });
  show();
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Open version verdicts (doesn't match)");
  expect(field).toHaveValue("true");
  await user.selectOptions(field, "false");
  expect(calls).toContainEqual(["PUT", "/admin/memory", { include_version_verdicts: false }]);
  await user.click(await screen.findByRole("button", { name: "Reset Open version verdicts (doesn't match)" }));
  expect(calls.map(([m, u]) => `${m} ${u}`)).toContain("DELETE /admin/memory/include_version_verdicts");
});
