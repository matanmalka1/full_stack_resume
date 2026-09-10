import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { CommitBar, NEXT_STEP_LABEL } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";

interface DraftApprovalBarProps {
  /* The step behind this one. It was a lone secondary link at the foot of the editor
     column - reachable only in the editing mode, and only after scrolling past the fact
     panels - so going back was a different gesture depending on what the reader happened
     to be looking at. */
  applicationHref: string;
  /* Null until a passing run describes the exact version on screen. It is the only thing
     that opens approval, and the sentence beside the button says so. */
  exactPassingRunId: string | null;
  onApprove: () => void;
  /* The projection's own blockers. Approval is refused by the backend either way; what
     the bar owes the reader is the reason it is shut, not a second rule. */
  reviewBlocked: boolean;
  /* An approval was refused because the draft moved after the run it named. */
  stale: boolean;
  validationResult?: string;
}

/* The one decision this screen exists for, in the place every step puts its action.

   Approval used to sit at the end of the validation panel, which is the foot of the
   shorter of two columns - on a laptop, below the fold, and in a different place in each
   of the three modes. A screen whose purpose is to read a document and sign it should not
   make the signature something the reader goes looking for. It is `CommitBar` now, the
   same surface the preparation and ready steps close with, so the answer to "what do I do
   now" is in one position across the whole flow rather than three.

   It decides nothing. `exactPassingRunId` is the panel's own report about the exact
   version, the blockers are the projection's, and the approval itself is the dialog's. */
export const DraftApprovalBar = ({
  applicationHref,
  exactPassingRunId,
  onApprove,
  reviewBlocked,
  stale,
  validationResult,
}: DraftApprovalBarProps) => {
  const reason = reviewBlocked
    ? "יש חסימה שדורשת החלטה לפני אישור."
    : stale
      ? "הטיוטה השתנתה מאז האימות. יש להריץ אימות חדש."
      : exactPassingRunId === null
        ? "האישור נפתח אחרי אימות שעבר על הגרסה המוצגת."
        : "האימות עבר על הגרסה המוצגת.";

  return (
    <CommitBar
      back={
        <Link className={buttonClasses("ghost")} to={applicationHref}>
          <ArrowRight aria-hidden="true" className="size-4" />
          חזרה להכנת קורות החיים
        </Link>
      }
      label={NEXT_STEP_LABEL}
      result={validationResult}
      primary={
        <Button disabled={exactPassingRunId === null} onClick={onApprove}>
          <ShieldCheck aria-hidden="true" className="size-4" />
          אישור הגרסה
        </Button>
      }
    >
      <p className="text-support leading-6 text-cv-text-muted" dir="auto">
        {reason}
      </p>
    </CommitBar>
  );
};
