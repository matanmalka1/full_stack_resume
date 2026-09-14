import type { ApplicationListItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { applicationLabel } from "@/features/applications";

interface DeleteApplicationDialogProps {
  application: ApplicationListItem | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/* Terminal and one-way: there is no undelete command in this phase, unlike closing,
   which `CloseApplicationDialog`'s undo button can reverse. The copy says so plainly
   and spells out what is untouched, so confirming here is not a surprise later. */
export const DeleteApplicationDialog = ({
  application,
  pending,
  onCancel,
  onConfirm,
}: DeleteApplicationDialogProps) => (
  <Dialog
    footer={
      <>
        <Button onClick={onCancel} variant="secondary">
          ביטול
        </Button>
        <Button onClick={onConfirm} pending={pending} pendingLabel="מוחק…" variant="destructive">
          מחיקת המועמדות
        </Button>
      </>
    }
    headingId="delete-application-heading"
    onClose={onCancel}
    open={application !== null}
    title="למחוק את המועמדות?"
  >
    <p dir="auto">
      {application === null
        ? null
        : `${applicationLabel(application.company, application.target_role)} תרד מלוח המועמדויות ולא תיספר עוד בברירת המחדל.`}
    </p>
    <p className="mt-2 text-support text-cv-text-muted">
      הפעולה סופית ואין לה ביטול. תצלום המשרה, הניתוח, הטיוטות, הגרסאות שאושרו וכל קובץ שהופק נשארים בדיוק כפי שהם
      ונגישים דרך הקישור הישיר של המועמדות - רק הרשימה מפסיקה להציג אותה.
    </p>
  </Dialog>
);
