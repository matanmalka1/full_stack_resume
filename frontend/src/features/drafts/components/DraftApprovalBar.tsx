import { ArrowRight, FileCheck2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Button, buttonClasses } from "@/ui/Button";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";

interface DraftApprovalBarProps {
  /* The step behind this one. It was a lone secondary link at the foot of the editor
     column - reachable only in the editing mode, and only after scrolling past the fact
     panels - so going back was a different gesture depending on what the reader happened
     to be looking at. */
  applicationHref: string;
  /* True while the stored check passed against the exact document on screen (§5
     `content_check = passed`). Approval also waits for saved edits and the projection's
     blockers to clear. */
  passing: boolean;
  onApprove: () => void;
  onValidate: () => void;
  validationPending: boolean;
  /* The projection's own blockers. Approval is refused by the backend either way; what
     the bar owes the reader is the reason it is shut, not a second rule. */
  reviewBlocked: boolean;
  unavailable?: boolean;
  /* An approval was refused because the document changed after the check it relied on. */
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

   It decides nothing. `passing` is the projection's report about the exact document, the
   blockers are the projection's, and the approval itself is the dialog's. */
export const DraftApprovalBar = ({
  applicationHref,
  passing,
  onApprove,
  onValidate,
  reviewBlocked,
  stale,
  validationResult,
  unavailable,
  validationPending,
}: DraftApprovalBarProps) => {
  const reason = reviewBlocked
    ? "יש חסימה שדורשת החלטה לפני הכנת הקובץ."
    : stale
      ? "הטיוטה השתנתה מאז הבדיקה. יש לבדוק את הגרסה הנוכחית מחדש."
      : unavailable
        ? "יש להשלים את שמירת העריכות לפני בדיקת הקובץ."
        : !passing
          ? "זה הצעד הסופי: בדיקה ואז אישור שמכין את ה־PDF. כדי רק לראות PDF, פתחו את PDF הטיוטה."
          : "הבדיקה עברה. האישור מכין את ה־PDF הסופי; עריכה אחריו תחזיר את המסמך לטיוטה.";

  const readyForApproval = passing && !reviewBlocked && !stale && !unavailable;

  return (
    <CommitBar
      back={
        <Link className={buttonClasses("ghost")} to={applicationHref}>
          <ArrowRight aria-hidden="true" className="size-icon-md" />
          חזרה לניתוח והתאמה
        </Link>
      }
      label={NEXT_STEP_LABEL}
      result={validationResult}
      primary={
        <Button
          disabled={reviewBlocked || unavailable || (!readyForApproval && validationPending)}
          onClick={readyForApproval ? onApprove : onValidate}
          pending={validationPending}
          pendingLabel="בודק את הקובץ…"
        >
          <FileCheck2 aria-hidden="true" className="size-icon-md" />
          {readyForApproval ? "אישור והכנת PDF" : stale ? "בדיקה מחדש והכנת PDF" : "בדיקה והכנת PDF"}
        </Button>
      }
    >
      <p className="text-support leading-6 text-cv-text-muted" dir="auto">
        {reason}
      </p>
    </CommitBar>
  );
};
