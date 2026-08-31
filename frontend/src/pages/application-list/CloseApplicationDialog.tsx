import type { ApplicationListItem } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";

interface CloseApplicationDialogProps {
  application: ApplicationListItem | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export const CloseApplicationDialog = ({
  application,
  pending,
  onCancel,
  onConfirm,
}: CloseApplicationDialogProps) => (
  <Dialog
    footer={
      <>
        <Button onClick={onCancel} variant="secondary">
          ביטול
        </Button>
        <Button onClick={onConfirm} pending={pending} pendingLabel="סוגר…">
          סגירת המועמדות
        </Button>
      </>
    }
    headingId="close-application-heading"
    onClose={onCancel}
    open={application !== null}
    title="לסגור את המועמדות?"
  >
    <p dir="auto">
      {application === null
        ? null
        : `${application.company} — ${application.target_role} תסומן כסגורה ותרד מלוח המועמדויות הפעילות.`}
    </p>
    <p className="mt-2 text-support text-cv-text-muted">
      שום דבר לא נמחק. תצלום המשרה, הטיוטות והגרסאות שאושרו נשמרים כפי שהם, והמועמדות
      נשארת נגישה דרך הסינון.
    </p>
  </Dialog>
);
