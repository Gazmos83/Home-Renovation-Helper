import { Download, FileBox, FileCode2, Image, Table2 } from "lucide-react";

/** One downloadable file of a version: its canonical name and the route that serves it. */
export type VersionFile = { name: string; href: string };

/**
 * What each canonical file holds, in the order the workshop tends to want them
 * (ported from the predecessor's "Download the package" panel, version-file-downloads).
 */
const FILE_NOTES: Record<string, { label: string; meta: string; icon: typeof FileBox }> = {
  "model.blend": { label: "Blender file", meta: "Millimetres · one named object per part", icon: FileBox },
  "model.glb": { label: "glTF model", meta: "glTF 2.0 · the same geometry, Y-up", icon: FileBox },
  "spec.json": { label: "Spec (JSON)", meta: "Dimensions, modules, layers and the cut list", icon: FileCode2 },
  "cutlist.csv": { label: "Cut list (CSV)", meta: "Every panel: quantity, L × W × T, material, grain, banding", icon: Table2 },
  "hardware.csv": { label: "Hardware (CSV)", meta: "Screws, hinges, pins and other fittings", icon: Table2 },
  "still.png": { label: "Still", meta: "The rendered still", icon: Image },
  "screenshot.png": { label: "Screenshot", meta: "The build's preview picture", icon: Image },
  "front.png": { label: "Front view", meta: "Straight-on front with dimension lines", icon: Image },
  "side.png": { label: "Side view", meta: "Straight-on side with dimension lines", icon: Image },
  "top.png": { label: "Top view", meta: "Straight-on top with dimension lines", icon: Image },
};

const ORDER = Object.keys(FILE_NOTES);

/** The saved name: `listening-wall-v18.blend`, `listening-wall-v18-cutlist.csv`. */
export function downloadName(owner: string, version: number, name: string): string {
  const stem = `${owner}-v${version}`;
  if (name === "model.blend") return `${stem}.blend`;
  if (name === "model.glb") return `${stem}.glb`;
  return `${stem}-${name}`;
}

/**
 * A version's files as download links. Every link addresses one canonical name on the
 * backend's file route, which refuses any other name; nothing here composes a path.
 */
export function VersionFiles({
  owner,
  version,
  files,
  heading = "Download the package",
  note,
}: {
  /** The piece's package id or the room's slug, used in the saved file names. */
  owner: string;
  version: number;
  files: VersionFile[];
  heading?: string;
  note?: string;
}) {
  const shown = ORDER.flatMap((name) => files.filter((file) => file.name === name));
  if (shown.length === 0) return null;
  return (
    <section aria-label={`${heading} (version ${version})`} className="grid gap-2">
      <h3 className="text-sm font-medium">{heading}</h3>
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
      <ul className="grid max-w-xl gap-2">
        {shown.map((file) => {
          const info = FILE_NOTES[file.name];
          const Icon = info.icon;
          return (
            <li key={file.name}>
              <a
                href={file.href}
                download={downloadName(owner, version, file.name)}
                aria-label={`Download ${info.label} (version ${version})`}
                className="flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors duration-150 hover:bg-muted"
              >
                <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm">{info.label}</span>
                  <span className="block text-xs text-muted-foreground">{info.meta}</span>
                </span>
                <Download aria-hidden className="size-4 text-muted-foreground" strokeWidth={1.75} />
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
