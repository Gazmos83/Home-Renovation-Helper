import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/lib/form";

/**
 * Approval of the version a Workspace pane shows (workspace-pane-approval): whether it is approved,
 * "Approve version N" when it is built and not approved, "Unapprove version N" when it is approved.
 * A version that is not built gets no control; a refusal is shown next to the control.
 */
export function ApprovalRow({
  label,
  version,
  approved,
  built,
  pending,
  error,
  onApprove,
  onUnapprove,
}: {
  /** What the group is named for screen readers, e.g. "Approval of Hall". */
  label: string;
  version: number;
  approved: boolean;
  built: boolean;
  pending: boolean;
  error: string | null;
  onApprove: () => void;
  onUnapprove: () => void;
}) {
  return (
    <div className="space-y-1" role="group" aria-label={label}>
      <div className="flex flex-wrap items-center gap-2">
        {approved ? (
          <span>
            <Badge>Approved</Badge> version {version}
          </span>
        ) : (
          <span className="text-sm text-muted-foreground">Version {version} is not approved.</span>
        )}
        {built && !approved && (
          <Button type="button" size="sm" disabled={pending} onClick={onApprove}>
            Approve version {version}
          </Button>
        )}
        {approved && (
          <Button type="button" size="sm" variant="outline" disabled={pending} onClick={onUnapprove}>
            Unapprove version {version}
          </Button>
        )}
      </div>
      <FieldError message={error} />
    </div>
  );
}
