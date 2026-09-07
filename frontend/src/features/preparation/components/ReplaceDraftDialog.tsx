import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";

interface ReplaceDraftDialogProps {
  commandsBlocked: boolean;
  keepPrevious: boolean;
  onClose: () => void;
  /* Sends the replacement with the answer the box currently holds. The dialog never
     reaches the command itself: what it owns is the decision, and the screen decides
     what to do with it. */
  onConfirm: () => void;
  onKeepPreviousChange: (keepPrevious: boolean) => void;
  open: boolean;
  pending: boolean;
}

/* The Keep decision is asked, not assumed, because it is the only choice here whose wrong
   answer cannot be undone: a replacement without it leaves manual wording with no
   historical copy, and nothing regenerates that. Not dismissible for the same reason -
   Escape must not stand for either answer. */
export const ReplaceDraftDialog = ({
  commandsBlocked,
  keepPrevious,
  onClose,
  onConfirm,
  onKeepPreviousChange,
  open,
  pending,
}: ReplaceDraftDialogProps) => (
  <Dialog
    dismissible={false}
    footer={
      <>
        <Button onClick={onClose} variant="secondary">
          ביטול
        </Button>
        <Button
          disabled={commandsBlocked}
          onClick={onConfirm}
          pending={pending}
          pendingLabel="מחליף טיוטה…"
          variant="primary"
        >
          החלפת הטיוטה
        </Button>
      </>
    }
    headingId="replace-working-draft-heading"
    onClose={onClose}
    open={open}
    title="החלפת הטיוטה הפעילה"
  >
    <div className="flex flex-col gap-3">
      <p>
        טיוטה חדשה תיבנה מהניתוח ומתוכנית הבחירה הפעילים. הטיוטה הנוכחית נשמרת כפי שהיא עד שההחלפה מצליחה, ואם היא נכשלת
        — היא נשארת בדיוק כפי שהייתה.
      </p>
      {/* What "nothing changes on failure" leaves out, and why it was not accurate. Keep
          writes its historical snapshot before the replacement starts, and the snapshot is
          an immutable record: it stays whether or not the run that followed it succeeded.
          That is the point of taking it first, but it means the reader is told what
          survives a failure rather than told nothing survives. */}
      <p className="text-support leading-6 text-cv-text-muted">
        עותק היסטורי, אם נבחר, נרשם לפני שההחלפה מתחילה — והוא נשמר גם אם ההחלפה נכשלת.
      </p>
      <Checkbox
        checked={keepPrevious}
        hint="העותק נשמר כרשומה היסטורית שאינה משתנה. בלעדיו, ניסוח ידני שנעשה בטיוטה הזאת לא יהיה ניתן לשחזור."
        onChange={(event) => onKeepPreviousChange(event.target.checked)}
      >
        שמירת עותק היסטורי של הטיוטה הנוכחית
      </Checkbox>
    </div>
  </Dialog>
);
