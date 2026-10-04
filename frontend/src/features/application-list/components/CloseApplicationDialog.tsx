import type { ApplicationListItem } from "@/api/contracts";
import { ConfirmDialog } from "@/ui/ConfirmDialog";
import { applicationLabel } from "@/features/application-detail";

interface CloseApplicationDialogProps {
  application: ApplicationListItem | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const CloseApplicationDialog = ({ application, pending, onCancel, onConfirm }: CloseApplicationDialogProps) => (
  <ConfirmDialog
    confirmLabel="סגירת המועמדות"
    headingId="close-application-heading"
    onCancel={onCancel}
    onConfirm={onConfirm}
    open={application !== null}
    pending={pending}
    pendingLabel="סוגר…"
    title="לסגור את המועמדות?"
  >
    <p dir="auto">
      {application === null
        ? null
        : `${applicationLabel(application.company, application.target_role)} תסומן כסגורה ותרד מלוח המועמדויות הפעילות.`}
    </p>
    <p className="mt-2 text-support text-cv-text-muted">
      שום דבר לא נמחק. תצלום המשרה, מסמך קורות החיים וההגשות נשמרים כפי שהם, והמועמדות נשארת נגישה דרך הסינון.
    </p>
  </ConfirmDialog>
);
