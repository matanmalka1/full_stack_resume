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
          <Button className="max-lg:order-last" onClick={onDiscardLocal} variant="secondary">
            שמירה על הגרסה הנוכחית
          </Button>
          <Button onClick={onReapplyLocal}>החלת הטקסט שלי על הגרסה הנוכחית</Button>
        </>
      }
      headingId="draft-conflict-heading"
      onClose={onDiscardLocal}
      open={open}
      title="הטיוטה השתנתה בזמן העריכה"
    >
      <p>
        גרסה חדשה יותר של הטיוטה נשמרה לפני השמירה שלך, ולכן השמירה נעצרה. שום דבר לא אוחד אוטומטית ושום טקסט לא נמחק.
      </p>

      <ul className="mt-3 flex flex-col gap-4">
        {pending.map((edit) => (
          /* Each text is its own panel - the reader's framed in the strong border, the
             saved one muted - so the two read as the two sides of the choice below them
             rather than as one paragraph. A phone stacks them; a desktop sets them side by
             side, the reader's own at the start, as its design does. */
          <li className="flex flex-col gap-2 lg:grid lg:grid-cols-2 lg:gap-3" key={edit.claim_id}>
            <div className="rounded-control border border-cv-border-strong p-card-padding">
              <p className="text-support font-medium text-cv-text lg:text-caption lg:font-bold lg:text-cv-text-muted">
                הטקסט שלי
              </p>
              <p className="text-body text-cv-text" dir="auto">
                {edit.text ?? ""}
              </p>
            </div>
            <div className="rounded-control border border-cv-border bg-cv-surface-muted p-card-padding">
              <p className="text-support font-medium text-cv-text lg:text-caption lg:font-bold lg:text-cv-text-muted">
                הגרסה הנוכחית
              </p>
              <p className="text-body text-cv-text-muted" dir="auto">
                {texts.get(edit.claim_id) ?? "השורה אינה קיימת עוד בגרסה הנוכחית."}
              </p>
            </div>
          </li>
        ))}
      </ul>

      {pendingRemovals.length === 0 ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          ההסרה שביקשת עדיין ממתינה. החלת הטקסט שלי תבצע גם אותה על הגרסה הנוכחית.
        </p>
      )}

      {pendingAdditions.length === 0 ? null : (
        <ul className="flex flex-col gap-2">
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
        <p className="text-support leading-6 text-cv-text-muted">
          שינויי הסדר שלך עדיין ממתינים. החלת הגרסה שלך תחיל גם אותם על הטיוטה הנוכחית, אם המבנה עדיין תואם.
        </p>
      )}
    </Dialog>
  );
};
