import { ShieldCheck } from "lucide-react";

import { ActionBar } from "../../ui/ActionBar";
import { Button } from "../../ui/Button";

interface DraftApprovalBarProps {
  /* Null until a passing run describes the exact version on screen. It is the only thing
     that opens approval, and the sentence beside the button says so. */
  exactPassingRunId: string | null;
  onApprove: () => void;
  /* The projection's own blockers. Approval is refused by the backend either way; what
     the bar owes the reader is the reason it is shut, not a second rule. */
  reviewBlocked: boolean;
  /* An approval was refused because the draft moved after the run it named. */
  stale: boolean;
}

/* The one decision this screen exists for, in a fixed place.

   Approval used to sit at the end of the validation panel, which is the foot of the
   shorter of two columns - on a laptop, below the fold, and in a different place in each
   of the three modes. A screen whose purpose is to read a document and sign it should not
   make the signature something the reader goes looking for. The bar is pinned instead, so
   the action is in the same place whatever the reader is doing, and it carries the reason
   it is shut rather than presenting a dead control.

   It decides nothing. `exactPassingRunId` is the panel's own report about the exact
   version, the blockers are the projection's, and the approval itself is the dialog's. */
export const DraftApprovalBar = ({ exactPassingRunId, onApprove, reviewBlocked, stale }: DraftApprovalBarProps) => {
  const reason = reviewBlocked
    ? "יש חסימה שדורשת החלטה לפני אישור."
    : stale
      ? "הטיוטה השתנתה מאז האימות. יש להריץ אימות חדש."
      : exactPassingRunId === null
        ? "האישור נפתח אחרי אימות שעבר על הגרסה המוצגת."
        : "האימות עבר על הגרסה המוצגת.";

  return (
    /* The sentence rides with the button rather than as a `secondary`: a bar with two
       sides is a split bar, and `ActionBar` drops its pinning for those. This is one
       action with its reason beside it. */
    <ActionBar
      className="justify-between"
      primary={
        <>
          <p className="text-support leading-6 text-cv-text-muted" dir="auto">
            {reason}
          </p>
          <Button disabled={exactPassingRunId === null} onClick={onApprove}>
            <ShieldCheck aria-hidden="true" className="size-4" />
            אישור הגרסה
          </Button>
        </>
      }
      sticky
    />
  );
};
