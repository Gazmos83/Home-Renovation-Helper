import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { ReadingTab } from "./ReadingTab";

/** installation-reading: the inspector's Reading tab. */

afterEach(() => vi.unstubAllGlobals());

const BASE = "/packages/hall-shelf/versions";
const NOTICE =
  "Recommended reading, not a safety approval. Fixing an item to a wall depends on the wall's substrate, the anchor and the load. NOT VERIFIED.";

const ENTRY = {
  version_id: "src-1",
  title: "DIN EN 14749:2022-07",
  publisher: "DIN Media",
  edition: "2022-07",
  standard_or_model: "EN 14749",
  page_section: "not recorded",
  jurisdiction: "EU",
  verification_status: "verified",
  source_url: "https://example.org/din-en-14749",
  items: ["hall-board"],
  matched_by: { "hall-board": "furniture: shelf" },
};

const LIST = {
  notice: NOTICE,
  items: [
    { id: "hall-board", name: "Hall board", kind: "wall_shelf" },
    { id: "upper", name: "Upper cabinet", kind: "wall_module" },
  ],
  entries: [ENTRY],
  gaps: [{ item: "upper", name: "Upper cabinet", reason: "No recorded source covers this item" }],
};

const STALE_REPORT = {
  report_id: "r-1",
  version: 3,
  overall: "INCOMPLETE",
  stale: true,
  stale_reasons: ["a newer geometry version exists"],
  conformity: "NOT_ESTABLISHED",
  snapshot: {
    evidence: {
      "src-1:p-1": {
        packet: { block: { pages: [4], section: "Fixing" }, text: "Synthetic fixing passage", metadata: { title: "Handbook" } },
      },
    },
  },
};

function serve({ reports = [] as unknown[], readable = true } = {}) {
  return stubFetch((call) => {
    if (call === `GET ${BASE}/3/reading`) return { body: LIST };
    if (call === `GET ${BASE}/3/reading/sources/src-1/blocks?page=1`)
      return {
        body: readable
          ? {
              version_id: "src-1",
              title: ENTRY.title,
              source_url: ENTRY.source_url,
              readable: true,
              reason: null,
              page: 1,
              more: false,
              blocks: [
                {
                  block_id: "p-1",
                  kind: "paragraph",
                  text: "Shelves shall be tested for strength.",
                  pages: [7],
                  printed_pages: [],
                  section: "5.2",
                  headers: [],
                  conditions: [],
                  verification_status: "verified",
                },
              ],
            }
          : { version_id: "src-1", title: null, source_url: ENTRY.source_url, readable: false, reason: "rights pending", page: 1, more: false, blocks: [] },
      };
    if (/^GET \/packages\/hall-shelf\/versions\/\d+\/engineering\/reports$/.test(call)) return { body: reports };
    return undefined;
  });
}

function show(version: number, approved: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReadingTab packageId="hall-shelf" version={version} approved={approved} />
    </QueryClientProvider>,
  );
}

test("an approved version lists its reading under the notice, and Read here shows the blocks", async () => {
  serve();
  show(3, true);

  expect(await screen.findByRole("note")).toHaveTextContent("NOT VERIFIED");
  const shelf = screen.getByRole("region", { name: "Hall board" });
  const link = within(shelf).getByRole("link", { name: ENTRY.title });
  expect(link).toHaveAttribute("href", ENTRY.source_url);
  expect(link).toHaveAttribute("target", "_blank");
  expect(within(shelf).getByText(/Edition: 2022-07/)).toBeInTheDocument();
  expect(within(shelf).getByText("Matched by furniture: shelf")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Upper cabinet" })).getByText("No recorded source covers this item")).toBeInTheDocument();

  await userEvent.click(within(shelf).getByRole("button", { name: "Read here" }));
  expect(await screen.findByText("Shelves shall be tested for strength.")).toBeInTheDocument();
  expect(screen.getByText("p. 7 · 5.2")).toBeInTheDocument();
  expect(screen.getByText("No engineering reports for this version.")).toBeInTheDocument();
});

test("a source that cannot be read here shows its reason", async () => {
  serve({ readable: false });
  show(3, true);

  await userEvent.click(await screen.findByRole("button", { name: "Read here" }));
  expect(await screen.findByText("Can't be read here: rights pending.")).toBeInTheDocument();
});

test("an unapproved version asks for approval and fetches no list", async () => {
  const calls = serve();
  show(4, false);

  expect(screen.getByText("Approve this version to see recommended reading")).toBeInTheDocument();
  await screen.findByText("No engineering reports for this version.");
  expect(calls.some(([, url]) => url.includes("/reading"))).toBe(false);
});

test("a stale report shows its reasons, the outcome and its local evidence", async () => {
  serve({ reports: [STALE_REPORT] });
  show(3, true);

  const reports = await screen.findByRole("region", { name: "Engineering reports" });
  expect(await within(reports).findByText("Outcome: INCOMPLETE · Conformity not established")).toBeInTheDocument();
  expect(within(reports).getByText("Stale: a newer geometry version exists")).toBeInTheDocument();
  expect(within(reports).getByText("Synthetic fixing passage")).toBeInTheDocument();
});

test("the tab shows no model, prompt, token or cost", async () => {
  serve({ reports: [STALE_REPORT] });
  const view = show(3, true);

  await screen.findByRole("note");
  await screen.findByText("Synthetic fixing passage");
  // "Standard or model" is a citation field, so model names are matched instead of the word.
  expect(view.container.textContent).not.toMatch(/deepseek|openai|anthropic|\bprompt|\btokens?\b|\bcost\b|\$/i);
});
