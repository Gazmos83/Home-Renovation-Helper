import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Offload from "./Offload";

const base = {
  configured: true, host: "gpu.example.org", port: 22, user: "render", blender: "/opt/blender/blender",
  device: "OPTIX", pinned_version: "5.2.1", target: "local", hourly_rate_eur: 1.8, benchmark: null, jobs: [],
};
const job = {
  package_id: "bench", version: 1, render: "turntable", estimate_seconds: 56, actual_seconds: 3600,
  transfer_seconds: 12.5, outcome: "succeeded", error: null, started_at: "2026-10-06T10:00:00Z", cost_eur: 1.8,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Offload /></QueryClientProvider>);
}

test("the server, the target and the recent jobs with their euro estimate are shown", async () => {
  stubFetch((call) => (call === "GET /admin/offload" ? { body: { ...base, jobs: [job] } } : undefined));
  show();
  expect(await screen.findByText("render@gpu.example.org:22 · Blender at /opt/blender/blender · OPTIX")).toBeInTheDocument();
  expect(screen.getByLabelText("Final renders")).toHaveValue("local");
  expect(screen.getByText("bench v1 turntable")).toBeInTheDocument();
  expect(screen.getByText("€1.80")).toBeInTheDocument();
  expect(screen.getByText("12.5 s")).toBeInTheDocument();
});

test("an unconfigured server says so and its actions are disabled", async () => {
  stubFetch((call) => (call === "GET /admin/offload" ? { body: { ...base, configured: false, host: null } } : undefined));
  show();
  expect(await screen.findByText(/Not configured/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Test the connection" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Run the remote benchmark" })).toBeDisabled();
});

test("a refusal of the target is shown next to the switch and the switch stays on local", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: { ...base, configured: false, host: null } };
    if (call === "PUT /admin/offload/target") {
      return { status: 422, body: { detail: { failure_class: "offload_not_configured", reason: "the render server is not configured, so finals cannot be sent there", field: "target" } } };
    }
  });
  show();
  await user.selectOptions(await screen.findByLabelText("Final renders"), "remote");
  const message = await screen.findByText("the render server is not configured, so finals cannot be sent there");
  expect(message.previousElementSibling).toBe(screen.getByLabelText("Final renders"));
  expect(screen.getByLabelText("Final renders")).toHaveValue("local");
});

test("a connection test shows reachability, version and GPUs", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: base };
    if (call === "POST /admin/offload/test") {
      return { body: { reachable: true, blender_version: "5.2.1", pinned_version: "5.2.1", version_ok: true, gpus: ["NVIDIA RTX 4090"] } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Test the connection" }));
  expect(await screen.findByText("Reachable · Blender 5.2.1 · GPUs: NVIDIA RTX 4090")).toBeInTheDocument();
});

test("the remote benchmark is run and its numbers shown", async () => {
  const user = userEvent.setup();
  let measured = false;
  stubFetch((call) => {
    if (call === "POST /admin/offload/benchmark") {
      measured = true;
      return { body: { ...base, benchmark: { seconds_per_megapixel: 0.2, overhead_seconds: 40, measured_at: "2026-10-06T10:00:00Z", calibrated: false } } };
    }
    if (call === "GET /admin/offload") {
      return { body: measured ? { ...base, benchmark: { seconds_per_megapixel: 0.2, overhead_seconds: 40, measured_at: "2026-10-06T10:00:00Z", calibrated: false } } : base };
    }
  });
  show();
  expect(await screen.findByText(/Not measured yet/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Run the remote benchmark" }));
  expect(await screen.findByText(/0\.200 s per megapixel \+ 40 s/)).toBeInTheDocument();
});

test("a failed benchmark shows its reason", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: base };
    if (call === "POST /admin/offload/benchmark") {
      return { status: 502, body: { detail: { failure_class: "benchmark_failed", reason: "the render server is unreachable" } } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Run the remote benchmark" }));
  expect(await screen.findByText("the render server is unreachable")).toBeInTheDocument();
});

test("a negative rate is refused next to the rate field", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: base };
    if (call === "PUT /admin/offload/rate") {
      return { status: 422, body: { detail: { failure_class: "refused", reason: "the hourly rate must not be negative", field: "hourly_rate_eur" } } };
    }
  });
  show();
  const field = await screen.findByLabelText(/Euros per hour/);
  await user.clear(field);
  await user.type(field, "-1");
  await user.click(screen.getByRole("button", { name: "Save the rate" }));
  expect((await screen.findByText("the hourly rate must not be negative")).previousElementSibling).toBe(field);
});
