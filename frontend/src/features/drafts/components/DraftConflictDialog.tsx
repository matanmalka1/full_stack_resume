import { Split } from "lucide-react";

import type { ClaimAddition, ClaimPatch } from "@/api/contracts";
import { outlineClaims } from "@/api/documents";
import type { EditableDocument } from "../model/drafts.types";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";

interface DraftConflictDialogProps {
  current: EditableDocument | undefined;
  onDiscardLocal: () => void;
  onReapplyLocal: () => void;
  open: boolean;
  pending: ClaimPatch[];
  pendingAdditions: ClaimAddition[];
  pendingRemovals: string[];
  pendingClaimOrders: Record<string, string[]>;
}

/* A.4: a 409 is a choice, never a merge and never a silent overwrite. The dialog shows
   the user's text against the current text for each claim it holds, and offers exactly
   two outcomes. It is not dismissible: Escape here would have to mean one of the two, and
   A.5 refuses a cancel that decides what happens to content. */
export const DraftConflictDialog = ({
  current,
  onDiscardLocal,
  onReapplyLocal,
  open,
  pending,
  pendingAdditions,
  pendingRemovals,
  pendingClaimOrders,
}: DraftConflictDialogProps) => {
  const texts = new Map(
    (current === undefined ? [] : outlineClaims(current.outline)).map((claim) => [claim.claim_id, claim.text]),
  );

  return (
    <Dialog
      dismissible={false}
      /* The two outcomes are long sentences: side by side on a phone each wrapped to
         three lines, so they stack there, one full-width command per line. */
      footerLayout="stack"
      footer={
        <>
          {/* On a phone the two outcomes stack, and the one that keeps the reader's own
              text leads: it is what they were in the middle of. The DOM order, and with it
              the desktop's, is unchanged. */}
          <Button className="max-lg:order-last" onClick={onDiscardLocal} size="default" variant="secondary">
            השארת הגרסה הנוכחית
          </Button>
          <Button onClick={onReapplyLocal} size="default">
            החלת הטקסט שלי על הגרסה הנוכחית
          </Button>
        </>
      }
      headingId="draft-conflict-heading"
      onClose={onDiscardLocal}
      open={open}
      size="wide"
      /* The design sets the mark beside the title rather than over it. Decorative: the
         title says it. */
      title={
        <span className="flex items-center gap-3.5">
          <span
            aria-hidden="true"
            className="flex size-11 shrink-0 items-center justify-center rounded-control bg-cv-text text-cv-canvas max-lg:size-10"
          >
            <Split className="size-icon-lg" />
          </span>
          הטיוטה השתנתה בזמן העריכה
        </span>
      }
    >
      {/* The title and the two answers say it to the eye: a newer version was saved
          first, nothing was merged and nothing deleted. Assistive tech hears it in full. */}
      <p className="sr-only">
        גרסה חדשה יותר של הטיוטה נשמרה לפני השמירה שלך, ולכן השמירה נעצרה. שום דבר לא אוחד אוטומטית ושום טקסט לא נמחק.
      </p>

      <ul className="flex flex-col gap-3.5">
        {pending.map((edit) => (
          /* Each text its own panel - the reader's framed in the strong edge, the saved
             one recessed - side by side where there is room, so the two read as the two
             sides of the choice below them. */
          <li className="grid gap-3.5 sm:grid-cols-2" key={edit.claim_id}>
            <div className="flex flex-col gap-2 rounded-control-lg border-[1.5px] border-cv-accent p-4">
              <p className="text-caption font-bold text-cv-text-muted">הטקסט שלי</p>
              <p className="text-body text-cv-text" dir="auto">
                {edit.text ?? ""}
              </p>
            </div>
            <div className="flex flex-col gap-2 rounded-control-lg border border-cv-hairline bg-cv-canvas p-4">
              <p className="text-caption font-bold text-cv-text-muted">הגרסה הנוכחית</p>
              <p className="text-body text-cv-accent" dir="auto">
                {texts.get(edit.claim_id) ?? "השורה אינה קיימת עוד בגרסה הנוכחית."}
              </p>
            </div>
          </li>
        ))}
      </ul>

      {pendingRemovals.length === 0 ? null : (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">
          ההסרה שביקשת עדיין ממתינה. החלת הטקסט שלי תבצע גם אותה על הגרסה הנוכחית.
        </p>
      )}

      {pendingAdditions.length === 0 ? null : (
        <ul className="mt-3 flex flex-col gap-2">
          {pendingAdditions.map((addition) => (
            <li
              className="text-support leading-6 text-cv-text-muted"
              dir="auto"
              key={`${addition.section}:${addition.text}`}
            >
              שורה חדשה שהוספתי ל"{addition.section}" עדיין ממתינה: {addition.text}
            </li>
          ))}
        </ul>
      )}

      {Object.keys(pendingClaimOrders).length === 0 ? null : (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">
          שינויי הסדר שלך עדיין ממתינים. החלת הגרסה שלך תחיל גם אותם על הטיוטה הנוכחית, אם המבנה עדיין תואם.
        </p>
      )}
    </Dialog>
  );
};
