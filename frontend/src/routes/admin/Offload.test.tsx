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

const podBase = {
  ...base, mode: "pod", host: null, port: null, user: "root", blender: "/workspace/blender-5.2.1-linux-x64/blender",
  pod: {
    gpu_types: ["NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"], image: "runpod/base:0.6.2", volume_id: "vol123", idle_minutes: 10,
    state: "none", pod_id: null, delete_at: null, error: null,
  },
  pod_sessions: [],
};

test("pod mode shows the pod settings and that no pod is running", async () => {
  stubFetch((call) => (call === "GET /admin/offload" ? { body: podBase } : undefined));
  show();
  expect(await screen.findByText(/RunPod pod · NVIDIA RTX A4500 > NVIDIA GeForce RTX 5090 · image runpod\/base:0.6.2 · volume vol123/)).toBeInTheDocument();
  expect(screen.getByText(/No pod running\. One is created after a final is approved and deleted after 10 idle minutes\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete pod now" })).toBeDisabled();
  expect(screen.getByLabelText("Minutes an idle pod is kept (1–120)")).toHaveValue("10");
  expect(screen.getByText("No pod has been created yet.")).toBeInTheDocument();
});

test("a running pod shows when it will be deleted and can be deleted now", async () => {
  const user = userEvent.setup();
  let deleted = false;
  const running = { ...podBase, pod: { ...podBase.pod, state: "running", pod_id: "pod1", delete_at: "2026-10-15T14:10:00+00:00" } };
  stubFetch((call) => {
    if (call === "POST /admin/offload/pod/delete") {
      deleted = true;
      return { body: podBase };
    }
    if (call === "GET /admin/offload") return { body: deleted ? podBase : running };
  });
  show();
  expect(await screen.findByText("Running (pod1) · deleted at 14:10 UTC if still idle")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Delete pod now" }));
  expect(await screen.findByText(/No pod running/)).toBeInTheDocument();
  expect(deleted).toBe(true);
});

test("a refused delete during a render is shown", async () => {
  const user = userEvent.setup();
  const running = { ...podBase, pod: { ...podBase.pod, state: "running", pod_id: "pod1", delete_at: null } };
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: running };
    if (call === "POST /admin/offload/pod/delete") {
      return { status: 409, body: { detail: { failure_class: "pod_busy", reason: "a render is running on the pod; it can be deleted when the render ends" } } };
    }
  });
  show();
  expect(await screen.findByText("Running (pod1) · a render is using it")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Delete pod now" }));
  expect(await screen.findByText("a render is running on the pod; it can be deleted when the render ends")).toBeInTheDocument();
});

test("a failed delete is shown with its error", async () => {
  const failed = { ...podBase, pod: { ...podBase.pod, state: "delete_failed", pod_id: "pod1", error: "RunPod answered 500" } };
  stubFetch((call) => (call === "GET /admin/offload" ? { body: failed } : undefined));
  show();
  expect(await screen.findByText(/Delete failed \(pod1\): RunPod answered 500\. Retried every minute/)).toBeInTheDocument();
});

test("an idle time out of range is refused next to the field", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: podBase };
    if (call === "PUT /admin/offload/idle") {
      return { status: 422, body: { detail: { failure_class: "refused", reason: "the idle time must be a whole number of minutes from 1 to 120", field: "idle_minutes" } } };
    }
  });
  show();
  const field = await screen.findByLabelText("Minutes an idle pod is kept (1–120)");
  await user.clear(field);
  await user.type(field, "0");
  await user.click(screen.getByRole("button", { name: "Save the idle time" }));
  expect(await screen.findByText("the idle time must be a whole number of minutes from 1 to 120")).toBeInTheDocument();
});

test("the pod connection test says no pod was started", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: podBase };
    if (call === "POST /admin/offload/test") return { body: { runpod_ok: true, volume_found: true, data_center: "EU-RO-1", reason: null } };
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Test the connection" }));
  expect(await screen.findByText("RunPod accepts the key · volume found in EU-RO-1 · no pod was started")).toBeInTheDocument();
});

test("pod sessions are listed with lifetime, jobs, outcome and cost", async () => {
  const session = {
    pod_id: "pod7", gpu_type: "NVIDIA GeForce RTX 5090", created_at: "2026-10-15T14:00:00+00:00",
    ready_at: "2026-10-15T14:02:30+00:00", deleted_at: "2026-10-15T14:30:00+00:00", lifetime_seconds: 1800,
    jobs: 2, outcome: "deleted_idle", error: null, cost_per_hr: 0.69, cost_usd: 0.35,
  };
  stubFetch((call) => (call === "GET /admin/offload" ? { body: { ...podBase, pod_sessions: [session] } } : undefined));
  show();
  expect(await screen.findByText("2026-10-15 14:00")).toBeInTheDocument();
  expect(screen.getByText("30 min 0 s")).toBeInTheDocument();
  expect(screen.getByText("deleted_idle")).toBeInTheDocument();
  expect(screen.getByText("$0.35")).toBeInTheDocument();
  expect(screen.getByText("NVIDIA GeForce RTX 5090")).toBeInTheDocument();
});

test("a failed benchmark with no reason still shows its status", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /admin/offload") return { body: podBase };
    if (call === "POST /admin/offload/benchmark") return { status: 504, body: "" };
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Run the remote benchmark" }));
  expect(await screen.findByText("the server answered 504")).toBeInTheDocument();
});

const week = {
  starts: 4, started_share: 0.75, median_startup_seconds: 90, placed: { "NVIDIA RTX A4500": 2, "NVIDIA GeForce RTX 4090": 1 },
  failed_starts: 1, samples: 100, any_in_stock_share: 0.62,
  per_type_share: { "NVIDIA GeForce RTX 4090": 0.24, "NVIDIA RTX A4500": 0.5 }, last_sample_at: "2026-10-15T16:00:00+00:00",
};
const empty = {
  starts: 0, started_share: null, median_startup_seconds: null, placed: {}, failed_starts: 0, samples: 0,
  any_in_stock_share: null, per_type_share: {}, last_sample_at: null,
};

test("availability shows both periods with starts and stock", async () => {
  stubFetch((call) => (call === "GET /admin/offload" ? { body: { ...podBase, availability: { "7": week, "30": empty }, stock_sampling: true } } : undefined));
  show();
  expect(await screen.findByText("Last 7 days")).toBeInTheDocument();
  expect(screen.getByText(/4 pod starts · 75% started · median start-up 90 s · 1 failed · placed: NVIDIA RTX A4500 ×2, NVIDIA GeForce RTX 4090 ×1/)).toBeInTheDocument();
  expect(screen.getByText(/62% of samples had at least one render GPU in stock \(100 samples, last 2026-10-15 16:00\)/)).toBeInTheDocument();
  expect(screen.getByText("NVIDIA GeForce RTX 4090: 24% · NVIDIA RTX A4500: 50%")).toBeInTheDocument();
  expect(screen.getByText("Last 30 days")).toBeInTheDocument();
  expect(screen.getByText("No pod starts yet.")).toBeInTheDocument();
  expect(screen.getByText("No stock samples yet.")).toBeInTheDocument();
});

test("stock sampling can be switched off", async () => {
  const user = userEvent.setup();
  let on = true;
  stubFetch((call, init) => {
    if (call === "PUT /admin/offload/sampling") {
      on = JSON.parse(String(init?.body)).on;
      return { body: { ...podBase, availability: { "7": empty, "30": empty }, stock_sampling: on } };
    }
    if (call === "GET /admin/offload") return { body: { ...podBase, availability: { "7": empty, "30": empty }, stock_sampling: on } };
  });
  show();
  const select = await screen.findByLabelText("Stock sampling every 15 minutes");
  expect(select).toHaveValue("on");
  await user.selectOptions(select, "off");
  expect(on).toBe(false);
  expect(await screen.findByLabelText("Stock sampling every 15 minutes")).toHaveValue("off");
});

test("host mode shows no availability section", async () => {
  stubFetch((call) => (call === "GET /admin/offload" ? { body: { ...base, availability: null, stock_sampling: null } } : undefined));
  show();
  await screen.findByText(/render@gpu.example.org/);
  expect(screen.queryByText("Availability")).not.toBeInTheDocument();
});
