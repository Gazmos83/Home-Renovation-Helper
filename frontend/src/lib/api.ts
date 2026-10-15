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

export type Question = { text: string; unit: string | null; choices: string[] };

/** A paused turn: a confirmation (subject, summary) or a question set (studio-chat-polish). */
export type Pending = {
  confirmation_id: string;
  kind?: "confirmation" | "questions";
  subject: string;
  summary: string;
  proposal: Record<string, unknown>;
  questions?: Question[];
};

export type AnswerRow = { question: string; answer: string };

export type ChatMessage = {
  role: "owner" | "assistant" | "confirmation" | "notice";
  text: string;
  /** `answers` is an answered question set, shown as its rows; a notice is a `render` or a `build` notice. */
  kind?: "text" | "answers" | "render" | "build" | "revision";
  rows?: AnswerRow[];
  upload_ids?: string[];
  /** An owner's message's id: the latest one can be edited. */
  message_id?: string;
  /** A render notice: its outcome and tier, and for a piece version the piece and version. */
  outcome?: "succeeded" | "failed";
  tier?: string;
  package_id?: string;
  version?: number;
};

export type ThreadDetail = Thread & { messages: ChatMessage[]; pending: Pending | null };

export type Turn = { reply: string; specialist: string | null; pending: Pending | null };

/** One step of a followed turn, as the streamed routes send it. */
export type TurnEvent =
  | { event: "specialist"; data: { role: string } }
  | { event: "tool"; data: { plugin: string } }
  | { event: "reply"; data: { reply: string; specialists: string[] } }
  | { event: "pending"; data: { pending: Pending; specialists: string[] } }
  | { event: "title"; data: { title: string } }
  | { event: "error"; data: { failure_class: string; reason: string } }
  /** The turn was stopped: it is removed from the thread; `text` says what had already started. */
  | { event: "stopped"; data: { text: string } }
  /** An edit rewound the thread; what the rewound turn confirmed stays. */
  | { event: "rewound"; data: { kept: string[] } }
  | { event: "done"; data: Record<string, never> };

/** The owner's answer to the pending item. */
export type ResumeBody =
  | { answer: "yes" | "no"; reason?: string }
  | { answers: string[] }
  | { declined: string };

/** One model call of a conversation (developer panel). */
export type ThreadCall = {
  time: string;
  slot: string;
  operation: string;
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated: boolean;
  /** The call's Langfuse trace page, when tracing is on and the call has one (dev-panel-insights). */
  trace_url?: string | null;
};

/** Call totals for a range of days, grouped per model, day and agent slot (dev-panel-insights). */
export type UsageGroup = {
  key: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_calls: number;
  cost_usd: number;
  cost_complete: boolean;
};

export type UsageSummary = {
  days: 7 | 30 | 90;
  cost_incomplete: boolean;
  label: string;
  tracing: boolean;
  model: UsageGroup[];
  day: UsageGroup[];
  slot: UsageGroup[];
};

export type ModelPriceRow = {
  slug: string;
  input_per_million_usd: number | null;
  output_per_million_usd: number | null;
  fetched_at: string | null;
};

export type WorkflowTool = {
  name: string;
  plugin: string;
  enabled: boolean;
  confirmation: boolean;
  render_guard: boolean;
};

export type WorkflowMap = {
  homeowner: string;
  entry: string;
  nodes: { name: string; model: string; tools: WorkflowTool[] }[];
  handoffs: { from: string; to: string }[];
};

export type GuidelineSourceRow = {
  id: string;
  origin: "list" | "upload";
  title: string;
  jurisdiction: string;
  published_on: string;
  licence: string;
  format: string;
  passages: number;
  deletable: boolean;
  size_bytes?: number;
  ingested_at?: string | null;
  error?: string | null;
};

export type NewGuidelineUpload = {
  file: File;
  title: string;
  jurisdiction: string;
  published_on: string;
  licence: string;
};

export type DesignRule = {
  id: string;
  origin: "file" | "edited" | "panel";
  valid: boolean;
  problem: string | null;
  applies_to: string;
  check: string;
  params: Record<string, unknown>;
  severity: "warn" | "refuse";
  source?: { publication: string; section: string; quote: string };
};

export type DesignRulesPayload = {
  rules: DesignRule[];
  checks: { name: string; applies_to: string }[];
};

export type OpenItem = { file: string; line: number; text: string };

/** The conversation's "decisions so far" note (conversation-memory-settings); no tokens or models. */
export type ConversationNote = { package_id: string | null; note: string | null; owner_edited: boolean };

export type MemorySettings = {
  trigger_percent: number;
  keep_turns: number;
  note_tokens: number;
  note_instructions: string;
  tool_result_chars: number;
  reviews: "auto" | "confirm";
  save_preferences: boolean;
  other_builds: "line" | "hidden";
  include_preferences: boolean;
  include_review_items: boolean;
  render_ratings: number;
  include_extension_requests: boolean;
};

export type MemoryPayload = { settings: MemorySettings; defaults: MemorySettings; fixed_rules: string[] };

export type Upload = { upload_id: string; kind: string; size_bytes: number; original_name: string };

/** The conversation's brief settings (split-project-panel). */
export type Brief = {
  confirmed: boolean;
  room: string | null;
  purpose: string | null;
  max_piece_height_mm: number | null;
  max_piece_height_from_version: number | null;
  style: string | null;
  budget_eur: number | null;
  /** The stored rooms the room can be chosen from. */
  rooms: string[];
};
export type BriefBody = {
  room: string | null;
  purpose: string;
  max_piece_height_mm: number | null;
  style: string | null;
  budget_eur: number | null;
};

export type ProgressStep = { step: string; done: boolean; detail: string | null };

export type Progress = {
  package_id: string | null;
  name: string | null;
  latest_version: number | null;
  approved_version: number | null;
  /** How many versions the piece holds, and the most it can. */
  version_count: number;
  max_versions: number;
  build_status: string | null;
  steps: ProgressStep[];
  next_step: string;
  open_review_items: number;
  open_requests: { field: string; request: string }[];
  screenshot: string | null;
  still: string | null;
  viewer: string | null;
  /** True while a render of the latest version is queued or running. */
  rendering: boolean;
  /**
   * The conversation's confirmed room or apartment, or `null` (project-room-inspection).
   * `slug` once a composition exists; `model` and `surfaces` when its latest version has a 3D model.
   */
  room?: {
    name: string;
    scope: "room" | "apartment";
    slug: string | null;
    model: string | null;
    surfaces: string | null;
    /** The composition's newest five versions, newest first. */
    versions?: CompositionVersion[];
    /** The composition's approved version number, or null when none is approved. */
    approved_version?: number | null;
    /** The approved version's picture, or null when none is approved or it has none. */
    approved_picture?: string | null;
  } | null;
};

export type ModelsPayload = {
  /** `alias`: the gateway redirects the slug to the newest model of its family. */
  registry: { slug: string; display_name: string; supports_images: boolean; alias: boolean }[];
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

/** One measured value of a hardware data sheet: a single number or a range, as its source gives it. */
export type HardwareMeasure = { value: number } | { min: number; max: number };

export type HardwareKind = "hinge" | "shelf_pin";

/** The drilling values of one hinge or shelf-pin item and the source they were read from (hardware-drilling). */
export type HardwareDataSheet = {
  id: string;
  key: string;
  kind: HardwareKind;
  maker: string;
  model: string;
  values: Record<string, unknown>;
  source_kind: "toom" | "manual";
  page_url: string | null;
  datasheet_url: string | null;
  citation: string;
  updated_at: string;
};

export type NewHardwareDataSheet = Omit<HardwareDataSheet, "id" | "updated_at">;

export type PieceSummary = {
  package_id: string;
  versions: number[];
  room: string | null;
  thread_id: string | null;
};

/** A measured room of the house file, with what deleting it would touch (rooms-page). */
export type RoomSummary = {
  name: string;
  width_mm: number;
  depth_mm: number;
  corners: number;
  height_mm: number;
  openings: number;
  apartment: string | null;
  pieces: { package_id: string; name: string }[];
  conversations: number;
  composition: { slug: string; versions: number[] } | null;
};

export type CompositionItem = {
  id: string;
  type: "piece" | "stand-in" | "model";
  name: string;
  version?: number;
  approved?: boolean;
  no_longer_approved?: boolean;
};

export type Composition = {
  scope: "room" | "apartment";
  name: string;
  slug: string;
  latest_version: number | null;
  status: string | null;
  items: CompositionItem[];
  picture: string | null;
  viewer: string | null;
  /** The latest version's `model.glb` and its build report (the surface map); absent on older versions. */
  model?: string | null;
  surfaces?: string | null;
  /** The newest five versions, newest first, for the version dropdown (project-room-inspection). */
  version_views?: CompositionVersion[];
  versions?: number[];
  approved_version?: number | null;
};

/** One listed composition version; the 3D routes are set only when it has `model.glb`. */
export type CompositionVersion = {
  version: number;
  status: string | null;
  picture: string | null;
  viewer: string | null;
  items: CompositionItem[];
  model: string | null;
  surfaces: string | null;
  dimensions: string | null;
  approved_at?: string | null;
};

/** PUT/DELETE `/compositions/{slug}/versions/{n}/approval`. */
export type CompositionVersionApproval = {
  slug: string;
  version: number;
  status: string | null;
  approved_at: string | null;
};

/** A composition version's unique walls and each room's ceiling height, in plan mm. */
export type RoomDimensions = {
  walls: { label: string; from: [number, number]; to: [number, number]; length_mm: number }[];
  ceilings: { room: string; height_mm: number; at: [number, number] }[];
};

/** What the Rooms page's 3D view reads from a composition's build report. */
export type CompositionReport = {
  /** Each surface the owner can switch, with the mesh names it holds. */
  surfaces: Record<string, string[]>;
  /** The rooms' plan bounds and the highest ceiling, in mm (x, y, z up). */
  extent_mm: { min: [number, number, number]; max: [number, number, number] };
};

/** A stored pricing of an approved version (cut-list-pricing); money in euro cents. */
export type Pricing = {
  id: string;
  package_id: string;
  version: number;
  computed_at: string;
  total_cents: number;
  complete: boolean;
  result: {
    /** Per material key: the sheets bought and the cut lines made from them. */
    materials: Record<
      string,
      {
        sheet_count?: number;
        cost_cents: number | null;
        cuts: { part_id: string; name: string; qty: number; status: string }[];
      }
    >;
    hardware: { id: string; item: string; qty: string; cost_cents: number | null }[];
    /** Every line with no price; named by whichever of its names it has. */
    unpriced: {
      kind: string;
      reason: string;
      name?: string;
      item?: string;
      label?: string;
      material_key?: string;
      key?: string;
    }[];
  };
};

export type ModelAsset = {
  model_id: string;
  name: string;
  kind: string;
  width_mm: number;
  depth_mm: number;
  height_mm: number;
  state: "checking" | "ready" | "refused";
  reason: string | null;
  measured_mm: { x: number; y: number; z: number } | null;
  triangles: number | null;
  /** The model file the others hang from: `model.glb`, or the zip's one `.gltf` or `.obj`. */
  entry: string;
  has_thumbnail: boolean;
};

export type VersionInfo = {
  package_id: string;
  version: number;
  status: string | null;
  approved_at: string | null;
  /** The version this one was revised from, when recorded in the house file. */
  revised_from?: number | null;
  /** The version's files present by name (front.png and friends only on newer builds). */
  files?: string[];
};

/** One cut-list row of a built version's `spec.json`. */
export type SpecPart = {
  id: string;
  name: string;
  qty: number;
  l: number;
  w: number;
  t: number;
  material: string;
  grain: string;
  banding: string;
  notes: string;
  module: string;
};

/** `""` when a missing data-sheet value leaves the quantity unknown (hardware-drilling). */
export type SpecHardware = { id: string; item: string; qty: number | ""; notes: string };

/** A drilling position: an exact value, a range, or its rule in words (hardware-drilling). */
export type DrillForm = { mm: number } | { min_mm: number; max_mm: number } | { rule: string };

export type DrillEntry = {
  calculation: string;
  part: string;
  what: string;
  /** The whole line the workshop reads, source included. */
  text: string;
  positions: { label: string; position: DrillForm; from: string }[];
  missing: string[];
  problem: string | null;
};

/** The drilling list a version was calculated with; absent on a version made before it existed. */
export type DrillingList = {
  calculated: true;
  complete: boolean;
  warnings: string[];
  counts: Record<string, number | null>;
  entries: DrillEntry[];
};

/** The parts of a built version's emitted `spec.json` the inspector reads (piece-inspector). */
export type PieceSpec = {
  name?: string;
  units?: string;
  overall: { w: number; h: number; d: number };
  /** Each module's size and position in mm, by module id. */
  modules?: Record<string, Record<string, number>>;
  /** Each module's display name, by module id. */
  module_names?: Record<string, string>;
  /** Mesh names under each layer. */
  layers: Record<string, string[]>;
  parts?: SpecPart[];
  hardware?: SpecHardware[];
  drilling?: DrillingList;
  /** The validated input the version was built from: where the model's centre is. */
  input?: { envelope?: unknown; wall_shelves?: { x: number; y: number }[] };
};

export type RenderItem = {
  render: string;
  label: string;
  tier: string | null;
  /** When the render last finished, for the newest-first order of the Renders tab. */
  finished_at: string | null;
  /** A turntable's frame count; 0 for a still. */
  frames: number;
  preview: string;
  viewer: string | null;
  can_rate: boolean;
  rating: "up" | "down" | null;
  comment: string | null;
};

/** One restyle picture of a version (restyle-variants): appearance only, never a render of the design. */
export type Variant = {
  id: string;
  label: string;
  tier: string | null;
  note: string | null;
  /** A piece variant: material slot name to look id. */
  looks: Record<string, string> | null;
  /** A room variant: the style id. */
  style: string | null;
  created_at: string | null;
  still: string;
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

export type OffloadPodSession = {
  pod_id: string;
  gpu_type: string;
  created_at: string;
  ready_at: string | null;
  deleted_at: string | null;
  lifetime_seconds: number;
  jobs: number;
  outcome: string;
  error: string | null;
  cost_per_hr: number | null;
  cost_usd: number | null;
};

export type OffloadPod = {
  gpu_types: string[];
  image: string;
  volume_id: string;
  idle_minutes: number;
  state: "none" | "starting" | "running" | "delete_failed";
  pod_id: string | null;
  delete_at: string | null;
  error: string | null;
};

/** One period of render GPU availability (render-gpu-availability); shares are 0–1, or null with nothing recorded. */
export type OffloadAvailability = {
  starts: number;
  started_share: number | null;
  median_startup_seconds: number | null;
  placed: Record<string, number>;
  failed_starts: number;
  samples: number;
  any_in_stock_share: number | null;
  per_type_share: Record<string, number | null>;
  last_sample_at: string | null;
};

export type OffloadSummary = {
  configured: boolean;
  mode: "host" | "pod" | null;
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
  pod: OffloadPod | null;
  pod_sessions: OffloadPodSession[];
  availability: { "7": OffloadAvailability; "30": OffloadAvailability } | null;
  stock_sampling: boolean | null;
};

export type OffloadTest = {
  reachable: boolean;
  blender_version: string | null;
  pinned_version: string;
  version_ok: boolean;
  gpus: string[];
};

/** Pod mode with no pod running: RunPod is asked about the key and the volume; no pod is created. */
export type OffloadRunPodTest = {
  runpod_ok: boolean;
  volume_found: boolean;
  data_center?: string;
  reason: string | null;
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

/** The refusal a non-2xx response carries, in the service's words. */
async function failure(response: Response): Promise<ApiError> {
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
  // An answer with neither a reason nor a status text (a dropped proxy, a bare 5xx) still says something.
  return new ApiError(response.status, field, message || `the server answered ${response.status}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    ...init,
    headers: init.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init.headers },
  });
  if (response.status === 401 && path !== "/auth/login") unauthorized.forEach((listener) => listener());
  if (!response.ok) throw await failure(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * A Server-Sent Events reader: feed it text as it arrives, in chunks of any size, and it
 * calls `onEvent` once per complete event, in order.
 */
export function sseParser(onEvent: (event: TurnEvent) => void) {
  let buffer = "";
  const flush = (block: string) => {
    let name = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (data.length) onEvent({ event: name, data: JSON.parse(data.join("\n")) } as TurnEvent);
  };
  return {
    push(chunk: string) {
      buffer += chunk.replaceAll("\r\n", "\n");
      let end = buffer.indexOf("\n\n");
      while (end !== -1) {
        flush(buffer.slice(0, end));
        buffer = buffer.slice(end + 2);
        end = buffer.indexOf("\n\n");
      }
    },
    end() {
      if (buffer.trim()) flush(buffer);
      buffer = "";
    },
  };
}

/** POST `body` to a streamed route and hand each event to `onEvent`; a refusal before the
 * stream opens is thrown as an `ApiError`, like any other request. */
async function stream(
  path: string,
  body: unknown,
  onEvent: (event: TurnEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (response.status === 401) unauthorized.forEach((listener) => listener());
  if (!response.ok) throw await failure(response);
  const parser = sseParser(onEvent);
  if (!response.body) {
    parser.push(await response.text());
    parser.end();
    return;
  }
  const reader = response.body.getReader();
  // An abort also ends a body that is still being read.
  const cancel = () => void reader.cancel();
  signal?.addEventListener("abort", cancel);
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
  } finally {
    signal?.removeEventListener("abort", cancel);
  }
  if (signal?.aborted) throw new DOMException("The turn is no longer followed.", "AbortError");
  parser.push(decoder.decode());
  parser.end();
}

const versionPath = (packageId: string, version: number) =>
  `/packages/${encodeURIComponent(packageId)}/versions/${version}`;

/** A built version's file, served by exact name. */
export const versionFile = (packageId: string, version: number, name: string) =>
  `${versionPath(packageId, version)}/files/${name}`;

/** A library model's stored file, and its preview picture (studio-tile-grid). */
export const modelFile = (modelId: string, name: string) =>
  `/models/${modelId}/files/${name.split("/").map(encodeURIComponent).join("/")}`;
export const modelThumbnail = (modelId: string) => `/models/${modelId}/thumbnail`;

/** Download links: plain URLs, so the browser sends the session cookie and saves the file. */
export const downloads = {
  importTemplate: "/design-import/template",
  design: (packageId: string, version: number) => `${versionPath(packageId, version)}/design`,
  bundle: (packageId: string, version: number) => `${versionPath(packageId, version)}/bundle`,
};

export type KnowledgeProperty = Record<string, unknown> & { id: string; verification_status: string; reviewed_by: string | null };
export type KnowledgeVersion = {
  id: string; key: string; metadata: Record<string, unknown> & { title: string; source_url: string | null; edition: string | null };
  collections: string[]; state: string; verification_status: string; reviewed_by: string | null;
  rights_status: string; grants: Record<string, unknown>; rights: Record<string, unknown>[];
  passages: number; properties: KnowledgeProperty[]; local_path: string | null; content_hash: string | null; superseded_by: string | null;
};
export type CatalogueEntry = { key: string; metadata: Record<string, unknown> & { title: string; edition?: string | null; source_url?: string | null } };
export type KnowledgeSearch = { evidence: Record<string, unknown>[]; metadata_only: Record<string, unknown>[]; limitation: string | null };
export type EngineeringMethod = { id: string; version: string; domain: string; units: string[]; required_inputs: string[]; citation_evidence_ids: string[]; criteria: { id: string; limit: number; unit: string; source_evidence_id: string }[]; independent_reference_cases: Record<string, unknown>[]; definition_hash: string; implemented: boolean; qualified_review_state: string; enabled: boolean; releasable: boolean; limitation: string | null };

export const api = {
  engineeringMethods: () => request<EngineeringMethod[]>("/admin/engineering-methods"),
  reviewEngineeringMethod: (id: string, data: unknown) => request<unknown>(`/admin/engineering-methods/${encodeURIComponent(id)}/review`, { method: "POST", body: JSON.stringify(data) }),
  knowledgeSources: () => request<KnowledgeVersion[]>("/admin/knowledge"),
  knowledgeCatalogue: () => request<CatalogueEntry[]>("/admin/knowledge/catalogue"),
  registerCatalogueEntry: (key: string) => request<KnowledgeVersion>(`/admin/knowledge/catalogue/${encodeURIComponent(key)}/register`, { method: "POST" }),
  ingestKnowledgeLink: (id: string) => request<{state: string; blocks: number; reason: string | null}>(`/admin/knowledge/${encodeURIComponent(id)}/ingest-link`, { method: "POST" }),
  registerKnowledge: (data: unknown) => request<KnowledgeVersion>("/admin/knowledge", { method: "POST", body: JSON.stringify(data) }),
  knowledgeRights: (id: string, data: unknown) => request<KnowledgeVersion>(`/admin/knowledge/${encodeURIComponent(id)}/rights`, { method: "POST", body: JSON.stringify(data) }),
  reviewKnowledge: (id: string, data: unknown) => request<KnowledgeVersion>(`/admin/knowledge/${encodeURIComponent(id)}/review`, { method: "POST", body: JSON.stringify(data) }),
  stageKnowledge: (id: string, file: File) => {
    const form = new FormData(); form.append("file", file);
    return request<KnowledgeVersion>(`/admin/knowledge/${encodeURIComponent(id)}/file`, { method: "POST", body: form });
  },
  ingestKnowledge: (id: string, blocks: unknown) => request<{state: string; blocks: number; reason: string | null}>(`/admin/knowledge/${encodeURIComponent(id)}/ingest`, { method: "POST", body: JSON.stringify(blocks) }),
  addKnowledgeProperty: (id: string, data: unknown) => request<KnowledgeVersion>(`/admin/knowledge/${encodeURIComponent(id)}/properties`, { method: "POST", body: JSON.stringify(data) }),
  editKnowledgeProperty: (id: string, data: unknown) => request<KnowledgeVersion>(`/admin/knowledge/properties/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(data) }),
  reviewKnowledgeProperty: (id: string, data: unknown) => request<KnowledgeVersion>(`/admin/knowledge/properties/${encodeURIComponent(id)}/review`, { method: "POST", body: JSON.stringify(data) }),
  supersedeKnowledge: (id: string, replacement: string) => request<KnowledgeVersion>(`/admin/knowledge/${encodeURIComponent(id)}/supersede/${encodeURIComponent(replacement)}`, { method: "POST" }),
  previewKnowledge: (data: unknown) => request<KnowledgeSearch>("/admin/knowledge/search", { method: "POST", body: JSON.stringify(data) }),
  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<{ email: string }>("/auth/me"),
  threads: () => request<Thread[]>("/chat/threads"),
  deleteThread: (threadId: string) =>
    request<void>(`/chat/threads/${threadId}`, { method: "DELETE" }),
  /** A new conversation; with no title, its first reply brings a generated one.
   * Pass `packageId` to bind it to an existing piece (refused when that piece already has one). */
  createThread: (title?: string, packageId?: string) =>
    request<Thread>("/chat/threads", {
      method: "POST",
      body: JSON.stringify({
        ...(title ? { title } : {}),
        ...(packageId ? { package_id: packageId } : {}),
      }),
    }),
  renameThread: (threadId: string, title: string) =>
    request<Thread>(`/chat/threads/${threadId}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  streamTurn: (
    threadId: string,
    message: string,
    uploadIds: string[],
    onEvent: (event: TurnEvent) => void,
    signal?: AbortSignal,
  ) => stream(`/chat/threads/${threadId}/turns/stream`, { message, upload_ids: uploadIds }, onEvent, signal),
  /** Replace the latest owner message and run it again; its files stay with it. */
  streamEdit: (
    threadId: string,
    messageId: string,
    message: string,
    onEvent: (event: TurnEvent) => void,
    signal?: AbortSignal,
  ) => stream(`/chat/threads/${threadId}/turns/latest`, { message_id: messageId, message }, onEvent, signal),
  /** Stop the running turn at its next step; its stream then ends with `stopped`. */
  stopTurn: (threadId: string) => request<{ stopping: boolean }>(`/chat/threads/${threadId}/turns/stop`, { method: "POST" }),
  streamResume: (threadId: string, confirmationId: string, answer: ResumeBody, onEvent: (event: TurnEvent) => void) =>
    stream(`/chat/threads/${threadId}/resume/stream`, { confirmation_id: confirmationId, ...answer }, onEvent),
  threadCalls: (threadId: string) => request<ThreadCall[]>(`/admin/threads/${threadId}/calls`),
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
  uploads: (threadId: string) => request<Upload[]>(`/chat/threads/${threadId}/uploads`),
  progress: (threadId: string) => request<Progress>(`/chat/threads/${threadId}/progress`),
  brief: (threadId: string) => request<Brief>(`/chat/threads/${threadId}/brief`),
  saveBrief: (threadId: string, body: BriefBody) =>
    request<Brief>(`/chat/threads/${threadId}/brief`, { method: "PUT", body: JSON.stringify(body) }),
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
  rooms: () => request<RoomSummary[]>("/rooms"),
  deleteRoom: (name: string) => request<void>(`/rooms/${encodeURIComponent(name)}`, { method: "DELETE" }),
  setPieceRoom: (packageId: string, room: string | null) =>
    request<{ package_id: string; room: string | null }>(`/packages/${encodeURIComponent(packageId)}/room`, {
      method: "PUT",
      body: JSON.stringify({ room }),
    }),
  compositions: () => request<Composition[]>("/compositions"),
  compositionReport: (url: string) => request<CompositionReport>(url),
  compositionDimensions: (url: string) => request<RoomDimensions>(url),
  approveCompositionVersion: (slug: string, version: number) =>
    request<CompositionVersionApproval>(
      `/compositions/${encodeURIComponent(slug)}/versions/${version}/approval`,
      { method: "PUT" },
    ),
  unapproveCompositionVersion: (slug: string, version: number) =>
    request<CompositionVersionApproval>(
      `/compositions/${encodeURIComponent(slug)}/versions/${version}/approval`,
      { method: "DELETE" },
    ),
  deleteCompositionVersion: (slug: string, version: number) =>
    request<void>(`/compositions/${encodeURIComponent(slug)}/versions/${version}`, { method: "DELETE" }),
  modelLibrary: () => request<ModelAsset[]>("/models"),
  uploadModel: (file: File, name: string, width: string, depth: string, height: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("name", name);
    form.append("width_mm", width);
    form.append("depth_mm", depth);
    form.append("height_mm", height);
    return request<ModelAsset>("/models", { method: "POST", body: form, headers: {} });
  },
  deleteModel: (modelId: string) => request<void>(`/models/${modelId}`, { method: "DELETE" }),
  storeModelThumbnail: (modelId: string, picture: Blob) =>
    request<void>(modelThumbnail(modelId), { method: "PUT", body: picture, headers: { "Content-Type": "image/png" } }),
  version: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}`),
  /** Every version of a piece, newest first, with its build state and approval. */
  piece: (packageId: string) =>
    request<{ package_id: string; versions: VersionInfo[] }>(`/packages/${encodeURIComponent(packageId)}`),
  pricings: (packageId: string, version: number) => request<Pricing[]>(`${versionPath(packageId, version)}/pricings`),
  /** A new pricing at the pricing defaults (no delivery, the store's cut-charge mode). */
  createPricing: (packageId: string, version: number) =>
    request<Pricing>(`${versionPath(packageId, version)}/pricings`, { method: "POST", body: JSON.stringify({}) }),
  pieceSpec: (packageId: string, version: number) =>
    request<PieceSpec>(versionFile(packageId, version, "spec.json")),
  approveVersion: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/approval`, {
      method: "PUT",
    }),
  unapproveVersion: (packageId: string, version: number) =>
    request<VersionInfo>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/approval`, {
      method: "DELETE",
    }),
  /** Delete one version with its renders, reviews and pricings; the last one deletes the piece. */
  deleteVersion: (packageId: string, version: number) =>
    request<void>(`/packages/${encodeURIComponent(packageId)}/versions/${version}`, { method: "DELETE" }),
  variants: (packageId: string, version: number) =>
    request<Variant[]>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/variants`),
  compositionVariants: (slug: string, version: number) =>
    request<Variant[]>(`/compositions/${encodeURIComponent(slug)}/versions/${version}/variants`),
  renders: (packageId: string, version: number) =>
    request<RenderItem[]>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders`),
  rateRender: (packageId: string, version: number, render: string, rating: "up" | "down", comment: string | null) =>
    request<RenderItem>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders/${encodeURIComponent(render)}/feedback`, {
      method: "PUT",
      body: JSON.stringify(comment ? { rating, comment } : { rating }),
    }),
  clearRating: (packageId: string, version: number, render: string) =>
    request<RenderItem>(`/packages/${encodeURIComponent(packageId)}/versions/${version}/renders/${encodeURIComponent(render)}/feedback`, {
      method: "DELETE",
    }),
  feedbackSummary: (days = 30) => request<FeedbackRow[]>(`/admin/feedback?days=${days}`),
  feedbackComments: (row: { slot: string | null; model: string | null; tier: string }) =>
    request<FeedbackComment[]>(
      `/admin/feedback/comments?tier=${encodeURIComponent(row.tier)}&slot=${encodeURIComponent(row.slot ?? "")}&model=${encodeURIComponent(row.model ?? "")}`,
    ),
  offload: () => request<OffloadSummary>("/admin/offload"),
  testOffload: () => request<OffloadTest | OffloadRunPodTest>("/admin/offload/test", { method: "POST" }),
  offloadBenchmark: () => request<OffloadSummary>("/admin/offload/benchmark", { method: "POST" }),
  setOffloadTarget: (target: "local" | "remote") =>
    request<OffloadSummary>("/admin/offload/target", { method: "PUT", body: JSON.stringify({ target }) }),
  setOffloadRate: (hourly_rate_eur: number) =>
    request<OffloadSummary>("/admin/offload/rate", { method: "PUT", body: JSON.stringify({ hourly_rate_eur }) }),
  setOffloadSampling: (on: boolean) =>
    request<OffloadSummary>("/admin/offload/sampling", { method: "PUT", body: JSON.stringify({ on }) }),
  deleteOffloadPod: () => request<OffloadSummary>("/admin/offload/pod/delete", { method: "POST" }),
  setOffloadIdle: (idle_minutes: number) =>
    request<OffloadSummary>("/admin/offload/idle", { method: "PUT", body: JSON.stringify({ idle_minutes }) }),
  usage: (days = 1) => request<UsageRow[]>(`/admin/usage?days=${days}`),
  usageSummary: (days: 7 | 30 | 90) => request<UsageSummary>(`/admin/usage/summary?days=${days}`),
  modelPrices: () => request<ModelPriceRow[]>("/admin/model-prices"),
  refreshModelPrices: () => request<ModelPriceRow[]>("/admin/model-prices/refresh", { method: "POST" }),
  workflow: () => request<WorkflowMap>("/admin/workflow"),
  guidelineSources: () => request<GuidelineSourceRow[]>("/admin/guidelines"),
  uploadGuideline: (upload: NewGuidelineUpload) => {
    const form = new FormData();
    form.append("file", upload.file);
    form.append("title", upload.title);
    form.append("jurisdiction", upload.jurisdiction);
    form.append("published_on", upload.published_on);
    form.append("licence", upload.licence);
    return request<GuidelineSourceRow>("/admin/guidelines", { method: "POST", body: form });
  },
  reingestGuideline: (id: string) =>
    request<GuidelineSourceRow>(`/admin/guidelines/${encodeURIComponent(id)}/ingest`, { method: "POST" }),
  deleteGuideline: (id: string) => request<void>(`/admin/guidelines/${encodeURIComponent(id)}`, { method: "DELETE" }),
  designRules: () => request<DesignRulesPayload>("/admin/rules"),
  saveDesignRule: (rule: Omit<DesignRule, "origin" | "valid" | "problem">) =>
    request<DesignRulesPayload>(`/admin/rules/${encodeURIComponent(rule.id)}`, {
      method: "PUT",
      body: JSON.stringify(rule),
    }),
  resetDesignRule: (id: string) =>
    request<DesignRulesPayload>(`/admin/rules/${encodeURIComponent(id)}`, { method: "DELETE" }),
  openItems: () => request<OpenItem[]>("/admin/open-items"),
  conversationNote: (threadId: string) => request<ConversationNote>(`/chat/threads/${threadId}/note`),
  saveConversationNote: (threadId: string, note: string) =>
    request<ConversationNote>(`/chat/threads/${threadId}/note`, { method: "PUT", body: JSON.stringify({ note }) }),
  decisionFromMessage: (threadId: string, text: string) =>
    request<{ topic: string; decision: string }>(`/chat/threads/${threadId}/note/decision`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  compressConversation: (threadId: string) =>
    request<ConversationNote>(`/chat/threads/${threadId}/note/compress`, { method: "POST" }),
  memorySettings: () => request<MemoryPayload>("/admin/memory"),
  saveMemorySettings: (changes: Partial<MemorySettings>) =>
    request<MemoryPayload>("/admin/memory", { method: "PUT", body: JSON.stringify(changes) }),
  resetMemorySetting: (field: keyof MemorySettings) =>
    request<MemoryPayload>(`/admin/memory/${field}`, { method: "DELETE" }),
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
  hardwareData: () => request<HardwareDataSheet[]>("/hardware-data"),
  createHardwareData: (sheet: NewHardwareDataSheet) =>
    request<HardwareDataSheet>("/hardware-data", { method: "POST", body: JSON.stringify(sheet) }),
  updateHardwareData: (id: string, sheet: Omit<NewHardwareDataSheet, "key">) =>
    request<HardwareDataSheet>(`/hardware-data/${id}`, { method: "PUT", body: JSON.stringify(sheet) }),
  deleteHardwareData: (id: string) => request<void>(`/hardware-data/${id}`, { method: "DELETE" }),
};
