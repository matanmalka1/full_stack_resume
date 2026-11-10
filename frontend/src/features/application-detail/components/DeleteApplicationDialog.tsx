import { Trash2 } from "lucide-react";

import { ConfirmDialog } from "@/ui/ConfirmDialog";
import { type NamedApplication, applicationSubject } from "../model/applicationPresentation";

interface DeleteApplicationDialogProps {
  application: NamedApplication | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/* Terminal and one-way: there is no undelete command in this phase, unlike closing. The
   copy says so plainly, in a tinted block of its own, and spells out what is untouched,
   so confirming here is not a surprise later. Asked from the board and from the hub. */
export const DeleteApplicationDialog = ({
  application,
  pending,
  onCancel,
  onConfirm,
}: DeleteApplicationDialogProps) => (
  <ConfirmDialog
    confirmLabel="מחיקת המועמדות"
    confirmVariant="destructive"
    icon={<Trash2 />}
    headingId="delete-application-heading"
    onCancel={onCancel}
    onConfirm={onConfirm}
    open={application !== null}
    pending={pending}
    pendingLabel="מוחק…"
    title="למחוק את המועמדות?"
  >
    <p className="text-label leading-relaxed text-cv-text" dir="auto">
      {application === null
        ? null
        : `${applicationSubject(application)} תרד מלוח המועמדויות ולא תיספר עוד בברירת המחדל.`}
    </p>
    <p className="mt-3 rounded-control bg-cv-surface-muted px-3.5 py-2.5 text-label leading-relaxed text-cv-text">
      הפעולה סופית ואין לה ביטול. תצלומי המשרה, הניתוחים, מסמך קורות החיים וכל קובץ שהופק נשארים בדיוק כפי שהם.
    </p>
  </ConfirmDialog>
);
