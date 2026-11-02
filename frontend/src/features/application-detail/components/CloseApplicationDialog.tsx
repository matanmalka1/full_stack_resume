import { Archive } from "lucide-react";

import { ConfirmDialog } from "@/ui/ConfirmDialog";
import { type NamedApplication, applicationSubject } from "../model/applicationPresentation";

interface CloseApplicationDialogProps {
  application: NamedApplication | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/* Closing ends the process with the employer and takes the card off the active board; it
   deletes nothing. The copy says both, so the question reads as the light one of the
   record's two endings. Asked from the board and from the hub alike. */
export const CloseApplicationDialog = ({ application, pending, onCancel, onConfirm }: CloseApplicationDialogProps) => (
  <ConfirmDialog
    confirmLabel="סגירת המועמדות"
    icon={<Archive />}
    headingId="close-application-heading"
    onCancel={onCancel}
    onConfirm={onConfirm}
    open={application !== null}
    pending={pending}
    pendingLabel="סוגר…"
    title="לסגור את המועמדות?"
  >
    <p className="text-label leading-relaxed text-cv-text" dir="auto">
      {application === null ? null : `${applicationSubject(application)} תסומן כסגורה ותרד מלוח המועמדויות הפעילות.`}
    </p>
    <p className="mt-2 text-label leading-relaxed text-cv-text-muted">
      שום דבר לא נמחק. נוסח המשרה, מסמך קורות החיים וההגשות נשמרים כפי שהם, והמועמדות נשארת נגישה דרך הסינון.
    </p>
  </ConfirmDialog>
);
