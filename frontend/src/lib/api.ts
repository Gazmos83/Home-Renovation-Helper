export type ToolToggle = {
  plugin: string;
  description: string;
  enabled: boolean;
  toggleable: boolean;
};

export type Thread = {
  thread_id: string;
  title: string;
  package_id: string | null;
  created_at: string;
  last_turn_at: string;
};

export type Pending = {
  confirmation_id: string;
  subject: string;
  summary: string;
  proposal: Record<string, unknown>;
};

export type ChatMessage = { role: "owner" | "assistant"; text: string };

export type ThreadDetail = Thread & { messages: ChatMessage[]; pending: Pending | null };

export type Turn = { reply: string; specialist: string | null; pending: Pending | null };

export type Upload = { upload_id: string; kind: string; size_bytes: number; original_name: string };

export type ProgressStep = { step: string; done: boolean; detail: string | null };

export type Progress = {
  package_id: string | null;
  name: string | null;
  latest_version: number | null;
  approved_version: number | null;
  build_status: string | null;
  steps: ProgressStep[];
  next_step: string;
  open_review_items: number;
  open_requests: { field: string; request: string }[];
  screenshot: string | null;
  still: string | null;
};

export type ModelsPayload = {
  registry: { slug: string; display_name: string; supports_images: boolean }[];
  slots: { slot: string; model: string; override: boolean }[];
  models: {
    slug: string;
    temperature: number | null;
    max_output_tokens: number | null;
    context_budget_tokens: number;
    daily_token_ceiling: number;
    usage_today: number;
  }[];
};

export type PluginRow = {
  name: string;
  description: string;
  kind: string;
  role: string;
  tools: string[];
  enabled: boolean;
  toggleable: boolean;
};

export type UsageRow = {
  model: string;
  day: string;
  input_tokens: number;
  output_tokens: number;
  calls: number;
};

export type PriceEntry = {
  key: string;
  label: string;
  category: string;
  unit: string;
  base_cents: number | null;
  provenance: "captured" | "manual" | "snapshot";
  source_url: string | null;
  captured_at: string | null;
  override_cents: number | null;
  override_note: string | null;
  effective_cents: number | null;
  unconfirmed: boolean;
};

export type NewEntry = {
  key: string;
  label: string;
  category: string;
  unit: string;
  base_cents: number | null;
  sheet_length_mm?: number;
  sheet_width_mm?: number;
  thickness_mm?: number;
};

export type Refresh = { outcome: string; reason: string | null; entry: PriceEntry | null };

export type Snapshot = {
  id: string;
  retailer: string;
  url: string;
  product_name: string;
  price: string | null;
  currency: string | null;
  availability: string | null;
  specification: string;
  store_name: string | null;
  captured_on: string;
};

export type NewSnapshot = Omit<Snapshot, "id" | "price"> & {
  price: string | null;
  prefill?: { key: string; category: string; unit: string };
};

export type Remnant = {
  id: string;
  material_key: string;
  length_mm: number;
  width_mm: number;
  grain_axis: "length" | "width";
  quantity: number;
};

export type NewRemnant = Omit<Remnant, "id">;

export type GuidelineNote = {
  id: string;
  title: string;
  body: string;
  value: number | null;
  unit: string | null;
  citation: string;
};

export type NewGuidelineNote = Omit<GuidelineNote, "id">;

export type PieceSummary = { package_id: string; versions: number[] };

export type VersionInfo = {
  package_id: string;
  version: number;
  status: string | null;
  approved_at: string | null;
};

export type RenderItem = {
  render: string;
  label: string;
  tier: string | null;
  preview: string;
  viewer: string | null;
  can_rate: boolean;
  rating: "up" | "down" | null;
  comment: string | null;
};

export type FeedbackRow = {
  slot: string | null;
  model: string | null;
  tier: string;
  up: number;
  down: number;
  latest_comment_at: string | null;
};

export type FeedbackComment = {
  package_id: string;
  version: number;
  render_key: string;
  rating: "up" | "down";
  comment: string;
  at: string;
};

export type OffloadJob = {
  package_id: string;
  version: number;
  render: string;
  estimate_seconds: number;
  actual_seconds: number | null;
  transfer_seconds: number | null;
  outcome: string;
  error: string | null;
  started_at: string;
  cost_eur: number | null;
};

export type OffloadSummary = {
  configured: boolean;
  host: string | null;
  port: number | null;
  user: string | null;
  blender: string | null;
  device: string | null;
  pinned_version: string;
  target: "local" | "remote";
  hourly_rate_eur: number | null;
  benchmark: {
    seconds_per_megapixel: number;
    overhead_seconds: number;
    measured_at: string;
    calibrated: boolean;
  } | null;
  jobs: OffloadJob[];
};

export type OffloadTest = {
  reachable: boolean;
  blender_version: string | null;
  pinned_version: string;
  version_ok: boolean;
  gpus: string[];
};

type Unauthorized = () => void;
const unauthorized = new Set<Unauthorized>();

/** Called when any request other than sign-in is answered 401; returns the unsubscribe. */
export function onUnauthorized(listener: Unauthorized): () => void {
  unauthorized.add(listener);
  return () => unauthorized.delete(listener);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public field: string | null,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: init.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init.headers },
  });
  if (response.status === 401 && path !== "/auth/login") unauthorized.forEach((listener) => listener());
  if (!response.ok) {
    let field: string | null = null;
    let message = response.statusText;
    try {
      const body = (await response.json()) as {
        detail?: { reason?: string; field?: string } | { loc: (string | number)[]; msg: string }[] | string;
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) {
        // FastAPI's own validation: the first problem, named by its last location part.
        const first = body.detail[0];
        if (first) {
          message = first.msg;
          field = String(first.loc[first.loc.length - 1]);
        }
      } else if (body.detail) {
        message = body.detail.reason ?? message;
        field = body.detail.field ?? null;
      }
    } catch {
      /* keep statusText */
    }
    throw new ApiError(response.status, field, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<{ email: string }>("/auth/me"),
  threads: () => request<Thread[]>("/chat/threads"),
  createThread: (title: string) =>
    request<Thread>("/chat/threads", { method: "POST", body: JSON.stringify({ title }) }),
  thread: (threadId: string) => request<ThreadDetail>(`/chat/threads/${threadId}`),
  sendTurn: (threadId: string, message: string, uploadIds: string[]) =>
    request<Turn>(`/chat/threads/${threadId}/turns`, {
      method: "POST",
      body: JSON.stringify({ message, upload_ids: uploadIds }),
    }),
  resume: (threadId: string, confirmationId: string, answer: "yes" | "no", reason: string | null) =>
    request<Turn>(`/chat/threads/${threadId}/resume`, {
      method: "POST",
      body: JSON.stringify(reason ? { confirmation_id: confirmationId, answer, reason } : { confirmation_id: confirmationId, answer }),
    }),
  upload: (threadId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    // No JSON header: the browser sets the multipart boundary itself.
    return request<Upload>(`/chat/threads/${threadId}/uploads`, { method: "POST", body: form, headers: {} });
  },
  progress: (threadId: string) => request<Progress>(`/chat/threads/${threadId}/progress`),
  tools: (threadId: string) => request<ToolToggle[]>(`/chat/threads/${threadId}/tools`),
  setTool: (threadId: string, plugin: string, enabled: boolean) =>
    request<ToolToggle>(`/chat/threads/${threadId}/tools/${plugin}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
  models: () => request<ModelsPayload>("/admin/models"),
  setRouting: (slot: string, model: string) =>
    request(`/admin/routing/${slot}`, { method: "PUT", body: JSON.stringify({ model }) }),
  setBudget: (slug: string, context_budget_tokens: number, daily_token_ceiling: number) =>
    request(`/admin/models/${slug}/budget`, {
      method: "PUT",
      body: JSON.stringify({ context_budget_tokens, daily_token_ceiling }),
    }),
  plugins: () => request<PluginRow[]>("/admin/plugins"),
  setPlugin: (name: string, enabled: boolean) =>
    request(`/admin/plugins/${name}`, { method: "PUT", body: JSON.stringify({ enabled }) }),
  invocations: (name: string) =>
    request<{ outcome: string; duration_ms: number | null }[]>(`/admin/plugins/${name}/invocations`),
  pieces: () => request<PieceSummary[]>("/packages"),
  version: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}`),
  approveVersion: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/approval`, {
      method: "PUT",
    }),
  unapproveVersion: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/approval`, {
      method: "DELETE",
    }),
  renders: (packageId: string, version: number) =>
    request<RenderItem[]>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders`),
  rateRender: (packageId: string, version: number, render: string, rating: "up" | "down", comment: string | null) =>
    request<RenderItem>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders/${render}/feedback`, {
      method: "PUT",
      body: JSON.stringify(comment ? { rating, comment } : { rating }),
    }),
  clearRating: (packageId: string, version: number, render: string) =>
    request<RenderItem>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders/${render}/feedback`, {
      method: "DELETE",
    }),
  feedbackSummary: (days = 30) => request<FeedbackRow[]>(`/admin/feedback?days=${days}`),
  feedbackComments: (row: { slot: string | null; model: string | null; tier: string }) =>
    request<FeedbackComment[]>(
      `/admin/feedback/comments?tier=${encodeURIComponent(row.tier)}&slot=${encodeURIComponent(row.slot ?? "")}&model=${encodeURIComponent(row.model ?? "")}`,
    ),
  offload: () => request<OffloadSummary>("/admin/offload"),
  testOffload: () => request<OffloadTest>("/admin/offload/test", { method: "POST" }),
  offloadBenchmark: () => request<OffloadSummary>("/admin/offload/benchmark", { method: "POST" }),
  setOffloadTarget: (target: "local" | "remote") =>
    request<OffloadSummary>("/admin/offload/target", { method: "PUT", body: JSON.stringify({ target }) }),
  setOffloadRate: (hourly_rate_eur: number) =>
    request<OffloadSummary>("/admin/offload/rate", { method: "PUT", body: JSON.stringify({ hourly_rate_eur }) }),
  usage: (days = 1) => request<UsageRow[]>(`/admin/usage?days=${days}`),
  priceList: (category?: string) =>
    request<PriceEntry[]>(category ? `/price-list?category=${encodeURIComponent(category)}` : "/price-list"),
  createEntry: (entry: NewEntry) => request<PriceEntry>("/price-list", { method: "POST", body: JSON.stringify(entry) }),
  entryFromUrl: (body: { url: string; key: string; category: string }) =>
    request<PriceEntry>("/price-list/from-url", { method: "POST", body: JSON.stringify(body) }),
  editEntry: (key: string, patch: { label?: string; base_cents?: number }) =>
    request<PriceEntry>(`/price-list/${encodeURIComponent(key)}`, { method: "PATCH", body: JSON.stringify(patch) }),
  setOverride: (key: string, cents: number, note: string | null) =>
    request<PriceEntry>(`/price-list/${encodeURIComponent(key)}/override`, {
      method: "PUT",
      body: JSON.stringify({ cents, note }),
    }),
  clearOverride: (key: string) =>
    request<PriceEntry>(`/price-list/${encodeURIComponent(key)}/override`, { method: "DELETE" }),
  refreshEntry: (key: string) =>
    request<Refresh>(`/price-list/${encodeURIComponent(key)}/refresh`, { method: "POST" }),
  snapshots: () => request<Snapshot[]>("/snapshots"),
  createSnapshot: (snapshot: NewSnapshot) =>
    request<Snapshot>("/snapshots", { method: "POST", body: JSON.stringify(snapshot) }),
  deleteSnapshot: (id: string) => request<void>(`/snapshots/${id}`, { method: "DELETE" }),
  remnants: () => request<Remnant[]>("/remnants"),
  addRemnant: (remnant: NewRemnant) => request<Remnant>("/remnants", { method: "POST", body: JSON.stringify(remnant) }),
  removeRemnant: (id: string) => request<void>(`/remnants/${id}`, { method: "DELETE" }),
  guidelineNotes: () => request<GuidelineNote[]>("/guideline-notes"),
  createNote: (note: NewGuidelineNote) =>
    request<GuidelineNote>("/guideline-notes", { method: "POST", body: JSON.stringify(note) }),
  updateNote: (id: string, note: NewGuidelineNote) =>
    request<GuidelineNote>(`/guideline-notes/${id}`, { method: "PUT", body: JSON.stringify(note) }),
  deleteNote: (id: string) => request<void>(`/guideline-notes/${id}`, { method: "DELETE" }),
};
