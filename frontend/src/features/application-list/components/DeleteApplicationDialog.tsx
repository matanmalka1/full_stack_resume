import type { ApplicationListItem } from "@/api/contracts";
import { ConfirmDialog } from "@/ui/ConfirmDialog";
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
  <ConfirmDialog
    confirmLabel="מחיקת המועמדות"
    confirmVariant="destructive"
    headingId="delete-application-heading"
    onCancel={onCancel}
    onConfirm={onConfirm}
    open={application !== null}
    pending={pending}
    pendingLabel="מוחק…"
    title="למחוק את המועמדות?"
  >
    <p dir="auto">
      {application === null
        ? null
        : `${applicationLabel(application.company, application.target_role)} תרד מלוח המועמדויות ולא תיספר עוד בברירת המחדל.`}
    </p>
    <p className="mt-2 text-support text-cv-text-muted">
      הפעולה סופית ואין לה ביטול. תצלומי המשרה, הניתוחים, מסמך קורות החיים, ההגשות וכל קובץ שהופק נשארים בדיוק כפי שהם
      ונגישים דרך הקישור הישיר של המועמדות - רק הרשימה מפסיקה להציג אותה.
    </p>
  </ConfirmDialog>
);
