import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Armchair, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PieceVariants } from "../components/Variants";
import { RenderRating } from "@/components/RenderRating";
import { api, downloads, versionFile, type PieceSummary, type Pricing, type RenderItem, type VersionInfo } from "../lib/api";
import { VersionFiles } from "@/components/studio/VersionFiles";
import { pictureVersion } from "../lib/pieces";
import { euros } from "../lib/money";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DeletePiece } from "@/components/DeletePiece";
import { DeleteVersion } from "@/components/DeleteVersion";
import { Tile } from "@/components/studio/Tile";
import { TileGrid } from "@/components/studio/TileGrid";
import { useStudioDialog } from "@/components/studio/useStudioDialog";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

function RenderCard({ packageId, version, item }: { packageId: string; version: number; item: RenderItem }) {
  return (
    <section className={cardClass} aria-label={item.label}>
      <div className="flex items-center gap-2">
        <h3>{item.label}</h3>
        {item.tier && <Badge variant="secondary">{item.tier}</Badge>}
      </div>
      <img src={item.preview} alt={`${item.label} of ${packageId} version ${version}`} className="max-h-72 rounded-md border" />
      <RenderRating packageId={packageId} version={version} item={item} />
    </section>
  );
}

/** A built version's actions: approve or unapprove, and open it in the inspector. */
function VersionActions({ packageId, version }: { packageId: string; version: number }) {
  const queryClient = useQueryClient();
  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
  });
  const change = useMutation({
    mutationFn: (approve: boolean) =>
      approve ? api.approveVersion(packageId, version) : api.unapproveVersion(packageId, version),
    onSuccess: () => {
      // Approving one version clears another, so every version of the piece is read again.
      queryClient.invalidateQueries({ queryKey: ["version", packageId] });
      queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  // No control until the version is read, and none for a version that is not built.
  if (!info.data || info.data.status !== "succeeded") return null;
  const approved = info.data.approved_at !== null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label={`Approval of ${packageId} version ${version}`}>
        {approved && <Badge>Approved</Badge>}
        <Button type="button" variant={approved ? "outline" : "default"} disabled={change.isPending} onClick={() => change.mutate(!approved)}>
          {approved ? "Unapprove" : "Approve"} version {version}
        </Button>
        <FieldError message={message(change.error)} />
      </div>
      <Button asChild variant="outline">
        <Link to={`/pieces/${encodeURIComponent(packageId)}/versions/${version}`}>Inspect version {version}</Link>
      </Button>
    </div>
  );
}

function unpricedName(line: Pricing["result"]["unpriced"][number]): string {
  return line.name ?? line.item ?? line.label ?? line.material_key ?? line.key ?? line.kind;
}

function PricingDetail({ pricing }: { pricing: Pricing }) {
  const materials = Object.entries(pricing.result.materials ?? {});
  const unpriced = pricing.result.unpriced ?? [];
  return (
    <div className="grid gap-2 text-sm">
      <p className="font-medium">Total: {euros(pricing.total_cents)}</p>
      {!pricing.complete && <p className="text-destructive">Pricing incomplete</p>}
      <h4>Sheets</h4>
      <ul>
        {materials.map(([material, entry]) => (
          <li key={material}>
            {material}: {entry.sheet_count ?? "no"} sheet{entry.sheet_count === 1 ? "" : "s"}, {euros(entry.cost_cents)}
          </li>
        ))}
      </ul>
      <h4>Cuts</h4>
      <ul>
        {materials.flatMap(([material, entry]) =>
          (entry.cuts ?? []).map((cut) => (
            <li key={`${material}-${cut.part_id}`}>
              {cut.qty} × {cut.name} ({material}, {cut.status})
            </li>
          )),
        )}
      </ul>
      <h4>Hardware</h4>
      <ul>
        {(pricing.result.hardware ?? []).map((line) => (
          <li key={line.id}>
            {line.qty} × {line.item}: {euros(line.cost_cents)}
          </li>
        ))}
      </ul>
      {unpriced.length > 0 && (
        <>
          <h4>Not priced</h4>
          <ul>
            {unpriced.map((line, index) => (
              <li key={index}>
                {unpricedName(line)}: {line.reason}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** An approved version's pricings, newest first, and a new one on request (Pieces page). */
function PricingPanel({ packageId, version }: { packageId: string; version: number }) {
  const queryClient = useQueryClient();
  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
  });
  const approved = Boolean(info.data?.approved_at);
  const key = ["pricings", packageId, version];
  const pricings = useQuery({ queryKey: key, queryFn: () => api.pricings(packageId, version), enabled: approved });
  const [chosen, setChosen] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api.createPricing(packageId, version),
    onSuccess: (made) => {
      queryClient.setQueryData<Pricing[]>(key, (listed) => [made, ...(listed ?? [])]);
      setChosen(made.id);
    },
  });
  if (!info.data) return null;
  const listed = pricings.data ?? [];
  const shown = listed.find((p) => p.id === chosen) ?? listed[0];
  return (
    <details className="min-w-0 rounded-md border p-2">
      <summary className="cursor-pointer">Pricing</summary>
      {!approved ? (
        <p className="text-sm">Version {version} must be approved before it can be priced.</p>
      ) : (
        <div className="mt-2 grid gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {listed.length > 0 && (
              <Select
                aria-label={`Pricings of ${packageId} version ${version}`}
                className="w-auto max-w-full min-w-0"
                value={shown?.id}
                onChange={(event) => setChosen(event.target.value)}
              >
                {listed.map((p) => (
                  <option key={p.id} value={p.id}>
                    {new Date(p.computed_at).toLocaleString()} — {euros(p.total_cents)}
                    {p.complete ? "" : " (incomplete)"}
                  </option>
                ))}
              </Select>
            )}
            <Button type="button" size="sm" disabled={create.isPending} onClick={() => create.mutate()}>
              Price this version
            </Button>
          </div>
          <FieldError message={message(create.error ?? pricings.error)} />
          {pricings.data && listed.length === 0 && <p className="text-sm">No pricing of this version yet.</p>}
          {shown && <PricingDetail pricing={shown} />}
        </div>
      )}
    </details>
  );
}

function Downloads({ packageId, version }: { packageId: string; version: number }) {
  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
  });
  const built = info.data?.status === "succeeded";
  return (
    <div className="grid gap-3">
      <p className="flex flex-wrap gap-2 text-sm" aria-label={`Downloads of ${packageId} version ${version}`}>
        <span>Downloads:</span>{" "}
        <a
          href={downloads.design(packageId, version)}
          download={`${packageId}-v${version}.json`}
          aria-label={`Download design (version ${version})`}
          className="underline"
        >
          Design (JSON)
        </a>
        {built && (
          <>
            {" "}
            <span aria-hidden>·</span>{" "}
            <a
              href={downloads.bundle(packageId, version)}
              download={`${packageId}-v${version}.zip`}
              aria-label={`Download bundle (version ${version})`}
              className="underline"
            >
              Bundle (ZIP)
            </a>
          </>
        )}
      </p>
      {built && (
        <VersionFiles
          owner={packageId}
          version={version}
          files={(info.data?.files ?? []).map((name) => ({ name, href: versionFile(packageId, version, name) }))}
        />
      )}
    </div>
  );
}

/**
 * Turntables and restyle variants are watched and rated on the inspector's Renders tab
 * (two-tier-renders); Pieces keeps the stills for rating.
 */
function isTurntableRender(render: string): boolean {
  return render === "turntable" || render.endsWith("-turntable") || render.startsWith("variant:");
}

function Version({ packageId, version }: { packageId: string; version: number }) {
  const renders = useQuery({
    queryKey: ["renders", packageId, version],
    queryFn: () => api.renders(packageId, version),
  });
  let shown;
  if (renders.error) shown = <FieldError message={message(renders.error)} />;
  else if (!renders.data) shown = <p>Loading…</p>;
  else {
    const cards = renders.data.filter((item) => !isTurntableRender(item.render));
    if (cards.length === 0) {
      shown = renders.data.length === 0 ? <p>No renders of this version yet.</p> : null;
    } else {
      shown = (
        <div className="grid gap-4 sm:grid-cols-2">
          {cards.map((item) => (
            <RenderCard key={item.render} packageId={packageId} version={version} item={item} />
          ))}
        </div>
      );
    }
  }
  return (
    <div className="grid gap-4">
      <VersionActions packageId={packageId} version={version} />
      <Downloads packageId={packageId} version={version} />
      <PricingPanel packageId={packageId} version={version} />
      {shown}
      <PieceVariants packageId={packageId} version={version} />
    </div>
  );
}

const NO_ROOM = "";

/** The room a piece is in, with a selector to attach it, move it or clear it. */
function RoomPicker({ id, room }: { id: string; room: string | null }) {
  const queryClient = useQueryClient();
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms });
  const choose = useMutation({
    mutationFn: (name: string) => api.setPieceRoom(id, name === NO_ROOM ? null : name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pieces"] }),
  });
  const label = `Room of ${id}`;
  return (
    <div className="grid gap-1">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>{room ? `Room: ${room}` : "No room"}</span>
        <Select
          aria-label={label}
          className="w-auto"
          value={room ?? NO_ROOM}
          disabled={choose.isPending}
          onChange={(event) => choose.mutate(event.target.value)}
        >
          <option value={NO_ROOM}>No room</option>
          {(rooms.data ?? []).map((room) => (
            <option key={room.name} value={room.name}>
              {room.name}
            </option>
          ))}
        </Select>
      </div>
      <FieldError message={message(choose.error)} />
    </div>
  );
}

/** A version dropdown entry: "Version N" and its state, if it has one (approved, failed, building). */
function versionLabel(version: number, info: VersionInfo | undefined): string {
  if (info?.approved_at) return `Version ${version} (approved)`;
  if (info?.status === "failed") return `Version ${version} (failed)`;
  if (info?.status === "queued" || info?.status === "running") return `Version ${version} (building)`;
  return `Version ${version}`;
}

/** Open this piece's conversation, or start one bound to it when it has none. */
function PieceConversation({ id, threadId }: { id: string; threadId: string | null }) {
  const navigate = useNavigate();
  const start = useMutation({
    mutationFn: () => api.createThread(undefined, id),
    onSuccess: (thread) => navigate(`/studio/workspace/${thread.thread_id}`),
  });
  if (threadId) {
    return (
      <Button asChild variant="outline" size="lg" className="w-fit font-semibold">
        <Link to={`/studio/workspace/${threadId}`}>Open conversation</Link>
      </Button>
    );
  }
  return (
    <div className="grid gap-1">
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="w-fit font-semibold"
        disabled={start.isPending}
        onClick={() => start.mutate()}
      >
        Start conversation
      </Button>
      <FieldError message={message(start.error)} />
    </div>
  );
}

/** Everything about one piece, shown in its dialog (studio-tile-grid): what its card held before. */
function PieceDetail({
  id,
  versions,
  room,
  threadId,
  onDeleted,
}: {
  id: string;
  versions: number[];
  room: string | null;
  threadId: string | null;
  onDeleted: () => void;
}) {
  const queryClient = useQueryClient();
  const [chosen, setVersion] = useState(versions[0]);
  // After a delete the chosen version may be gone: show the newest left.
  const version = versions.includes(chosen) ? chosen : versions[0];
  const infos = useQueries({
    queries: versions.map((n) => ({
      queryKey: ["version", id, n],
      queryFn: () => api.version(id, n),
    })),
  });
  const approved = infos.find((q) => q.data?.approved_at)?.data?.version;
  const shown = infos[versions.indexOf(version)]?.data;
  // The approved version's screenshot, else the newest one's: it does not follow the dropdown.
  const picture = pictureVersion(infos.map((q) => q.data));
  return (
    <>
      <DialogHeader>
        <DialogTitle>{id}</DialogTitle>
      </DialogHeader>
      <PieceConversation id={id} threadId={threadId} />
      {picture && (
        <figure className="grid w-fit gap-1">
          <img
            src={versionFile(id, picture.version, "screenshot.png")}
            alt={`${id} version ${picture.version}`}
            className="max-h-48 rounded-md border object-contain"
          />
          <figcaption className="text-sm text-muted-foreground">
            Version {picture.version}
            {picture.approved ? " (approved)" : ""}
          </figcaption>
        </figure>
      )}
      <p className="text-sm text-muted-foreground">
        {approved ? `Approved: version ${approved}` : "No version approved yet."}
      </p>
      <RoomPicker id={id} room={room} />
      <Select
        aria-label={`Versions of ${id}`}
        className="w-auto max-w-full min-w-0"
        value={version}
        onChange={(event) => setVersion(Number(event.target.value))}
      >
        {versions.map((n, index) => (
          <option key={n} value={n}>
            {versionLabel(n, infos[index]?.data)}
          </option>
        ))}
      </Select>
      {shown && !shown.approved_at && (
        <DeleteVersion
          key={version}
          packageId={id}
          version={version}
          only={versions.length === 1}
          onDeleted={() => {
            queryClient.removeQueries({ queryKey: ["version", id, version] });
            queryClient.invalidateQueries({ queryKey: ["pieces"] });
          }}
        />
      )}
      <Version packageId={id} version={version} />
      <DeletePiece packageId={id} onDeleted={onDeleted} />
    </>
  );
}

/**
 * The Pieces intro and how the import template is used, behind an information button so the header stays
 * one row and the grid fills the screen (studio-tile-grid). It floats over the grid, as wide as the header row.
 */
function PiecesHelp() {
  const [open, setOpen] = useState(false);
  return (
    <span
      onBlur={(event) => !event.currentTarget.contains(event.relatedTarget) && setOpen(false)}
      onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="size-8 p-0"
        aria-label="About pieces and the import template"
        aria-expanded={open}
        aria-controls="pieces-help"
        onClick={() => setOpen(!open)}
      >
        <Info aria-hidden size={18} />
      </Button>
      {open && (
        <span
          id="pieces-help"
          role="note"
          className="absolute inset-x-0 top-full z-20 mt-1 grid max-w-md gap-2 rounded-md border bg-popover p-3 text-sm text-popover-foreground shadow-md"
        >
          <span>Your designs and their renders. Tell us what you think of a render; it helps the next one.</span>
          <span>
            The import template: give it to another AI chat to fill in, then attach the file it returns in a new
            conversation.
          </span>
        </span>
      )}
    </span>
  );
}

/** A piece's tile: the picture the card chose, its caption, and "Approved" when a version is. */
function PieceTile({ piece, onOpen }: { piece: PieceSummary; onOpen: () => void }) {
  const queryClient = useQueryClient();
  const infos = useQueries({
    queries: piece.versions.map((n) => ({
      queryKey: ["version", piece.package_id, n],
      queryFn: () => api.version(piece.package_id, n),
    })),
  });
  const picture = pictureVersion(infos.map((q) => q.data));
  const approved = infos.some((q) => q.data?.approved_at);
  const newest = piece.versions[0];
  return (
    <Tile
      name={piece.package_id}
      picture={picture ? versionFile(piece.package_id, picture.version, "screenshot.png") : null}
      detail={picture ? `Version ${picture.version}${picture.approved ? " (approved)" : ""}` : undefined}
      placeholder={Armchair}
      badge={approved ? <Badge>Approved</Badge> : undefined}
      onOpen={onOpen}
      // The dialog opens on the newest version's renders; start loading them now.
      onPrefetch={() =>
        newest !== undefined &&
        queryClient.prefetchQuery({
          queryKey: ["renders", piece.package_id, newest],
          queryFn: () => api.renders(piece.package_id, newest),
        })
      }
    />
  );
}

export default function Pieces() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const dialog = useStudioDialog("pieces");
  const pieces = useQuery({ queryKey: ["pieces"], queryFn: api.pieces });
  const create = useMutation({
    mutationFn: () => api.createThread(),
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      navigate(`/studio/workspace/${thread.thread_id}`);
    },
  });
  const wanted = dialog.segments.length === 1 ? dialog.segments[0] : null;
  const opened = pieces.data?.find((piece) => piece.package_id === wanted);
  // An address naming no piece (unknown, or its last version just deleted) shows the grid.
  const missing = Boolean(pieces.data) && dialog.segments.length > 0 && !opened;
  useEffect(() => {
    if (missing) dialog.dismiss();
  }, [missing]);
  if (pieces.error) {
    return <FieldError message={message(pieces.error)} />;
  }
  if (!pieces.data) return <p>Loading…</p>;
  return (
    <>
      <div className="relative flex flex-wrap items-center gap-x-4 gap-y-2">
        <Button type="button" disabled={create.isPending} onClick={() => create.mutate()}>
          Create A New Piece
        </Button>
        <a
          href={downloads.importTemplate}
          download="import-template.json"
          aria-label="Download the import template"
          className="text-sm underline"
        >
          Import template
        </a>
        <PiecesHelp />
      </div>
      <FieldError message={message(create.error)} />
      {pieces.data.length === 0 && (
        <p>No pieces yet. Use Create A New Piece to start a conversation and describe one.</p>
      )}
      <TileGrid label="Pieces" items={pieces.data} keyOf={(piece) => piece.package_id}>
        {(piece) => <PieceTile piece={piece} onOpen={() => dialog.open(piece.package_id)} />}
      </TileGrid>
      <Dialog open={Boolean(opened)} onOpenChange={(open) => !open && dialog.close()}>
        {opened && (
          <DialogContent aria-describedby={undefined}>
            <PieceDetail
              key={opened.package_id}
              id={opened.package_id}
              versions={opened.versions}
              room={opened.room}
              threadId={opened.thread_id}
              onDeleted={() => {
                queryClient.removeQueries({ queryKey: ["version", opened.package_id] });
                queryClient.invalidateQueries({ queryKey: ["pieces"] });
                queryClient.invalidateQueries({ queryKey: ["threads"] });
                queryClient.invalidateQueries({ queryKey: ["compositions"] });
                dialog.dismiss();
              }}
            />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
