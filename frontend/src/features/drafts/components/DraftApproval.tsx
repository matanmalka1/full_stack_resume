import { Check } from "lucide-react";

import { Button } from "@/ui/Button";
import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";

export interface DraftApprovalState {
  /* True while the stored check passed against the exact document on screen (§5
     `content_check = passed`). Approval also waits for saved edits and the projection's
     blockers to clear. */
  passing: boolean;
  onApprove: () => void;
  onValidate: () => void;
  /* The projection's own blockers. Approval is refused by the backend either way; what
     the screen owes the reader is the reason it is shut, not a second rule. */
  reviewBlocked: boolean;
  /* An approval was refused because the document changed after the check it relied on. */
  stale: boolean;
  unavailable: boolean;
  validationPending: boolean;
  /* The outcome of the last press, said once. */
  validationResult?: string;
}

const readyForApproval = (state: DraftApprovalState): boolean =>
  state.passing && !state.reviewBlocked && !state.stale && !state.unavailable;

/* The one decision this screen exists for: in the heading's row on a wide screen and
   pinned to a phone's bottom edge, as the design places it - one command, the same words
   at both widths.

   It decides nothing. A press runs the check when the document on screen has not passed
   one, and opens the approval once it has; `passing` is the projection's report about the
   exact document, the blockers are the projection's, and the approval itself is the
   dialog's. */
export const DraftApproveButton = ({
  size = "default",
  state,
}: {
  /* "large" is the 52px command a phone's pinned bar leads with. */
  size?: "default" | "large";
  state: DraftApprovalState;
}) => {
  const ready = readyForApproval(state);
  return (
    <Button
      className="shadow-action"
      disabled={state.reviewBlocked || state.unavailable || (!ready && state.validationPending)}
      onClick={ready ? state.onApprove : state.onValidate}
      pending={state.validationPending}
      pendingLabel="בודק את הקובץ…"
      size={size}
    >
      <Check aria-hidden="true" className={size === "large" ? "size-icon-lg" : "size-icon-md"} />
      אישור הטיוטה ויצירת הקובץ
    </Button>
  );
};

/* Why the command is shut or must run again, and what its last press found - kept beside
   the fit and the save state rather than in a bar of its own. Silent while there is
   nothing to say; the result is the region's one announcement. */
export const DraftApprovalNote = ({ className, state }: { className?: string; state: DraftApprovalState }) => {
  const reason = state.reviewBlocked
    ? "יש חסימה שדורשת החלטה לפני הכנת הקובץ."
    : state.stale
      ? "הטיוטה השתנתה מאז הבדיקה. יש לבדוק את הגרסה הנוכחית מחדש."
      : state.unavailable
        ? "יש להשלים את שמירת העריכות לפני בדיקת הקובץ."
        : undefined;
  const result = state.validationResult;
  const silent = reason === undefined && result === undefined;

  /* Silent, the block has no box and its region is set out of the flow, so the column
     it stands in spaces nothing around it - while the region stays mounted to announce
     the next result. */
  return (
    <div
      className={cx(
        silent
          ? "contents"
          : "flex flex-col gap-1 rounded-control-lg border border-cv-hairline bg-cv-surface px-3.5 py-3 text-support leading-6",
        !silent && className,
      )}
    >
      {reason === undefined ? null : (
        <p className="text-cv-text-muted" dir="auto">
          {reason}
        </p>
      )}
      <LiveRegion className="font-medium text-cv-text" visuallyHidden={result === undefined}>
        {result}
      </LiveRegion>
    </div>
  );
};
