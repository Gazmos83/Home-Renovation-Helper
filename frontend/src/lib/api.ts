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
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let field: string | null = null;
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: { reason?: string; field?: string } | string };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail) {
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
  usage: (days = 1) => request<UsageRow[]>(`/admin/usage?days=${days}`),
};
