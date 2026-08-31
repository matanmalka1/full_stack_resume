import type { ClaimPatch, WorkingDraft } from "../../api/contracts";
import { outlineClaims } from "../../api/drafts";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";

interface DraftConflictDialogProps {
  current: WorkingDraft | undefined;
  onDiscardLocal: () => void;
  onReapplyLocal: () => void;
  open: boolean;
  pending: ClaimPatch[];
  pendingRemovals: string[];
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
  pendingRemovals,
}: DraftConflictDialogProps) => {
  const texts = new Map(
    (current === undefined ? [] : outlineClaims(current)).map((claim) => [
      claim.claim_id,
      claim.text,
    ]),
  );

  return (
    <Dialog
      dismissible={false}
      footer={
        <>
          <Button onClick={onDiscardLocal} variant="secondary">
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
        גרסה חדשה יותר של הטיוטה נשמרה לפני השמירה שלך, ולכן השמירה נעצרה. שום דבר לא אוחד אוטומטית
        ושום טקסט לא נמחק.
      </p>

      <ul className="flex flex-col gap-4">
        {pending.map((edit) => (
          <li className="flex flex-col gap-2" key={edit.claim_id}>
            <div>
              <p className="text-support font-medium text-cv-text">הטקסט שלי</p>
              <p className="text-body text-cv-text" dir="auto">
                {edit.text ?? ""}
              </p>
            </div>
            <div>
              <p className="text-support font-medium text-cv-text">הגרסה הנוכחית</p>
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
    </Dialog>
  );
};
