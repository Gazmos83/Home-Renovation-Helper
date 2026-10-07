import { X } from "lucide-react";
import type { Upload } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/** An attached file: a thumbnail for an image, a named chip for a design file or a note. */
export function Attachment({ upload }: { upload: Upload }) {
  if (upload.kind === "design" || upload.kind === "text") {
    const what = upload.kind === "design" ? "Design file" : "Note";
    return (
      <Badge variant="secondary" aria-label={`${what} ${upload.original_name}`}>
        {upload.original_name}
      </Badge>
    );
  }
  return <img src={`/uploads/${upload.upload_id}`} alt={upload.original_name} className="h-16 rounded-md border" />;
}

/** An attachment on the composer, with its remove control. */
export function PendingAttachment({ upload, onRemove }: { upload: Upload; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1">
      <Attachment upload={upload} />
      <Button type="button" variant="ghost" size="sm" className="h-6 px-1" aria-label={`Remove ${upload.original_name}`} onClick={onRemove}>
        <X aria-hidden size={14} />
      </Button>
    </span>
  );
}
