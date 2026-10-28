import { RefreshCw } from "lucide-react";

import { ConfirmDialog } from "@/ui/ConfirmDialog";

interface BuildFromAnalysisDialogProps {
  commandsBlocked: boolean;
  onClose: () => void;
  /* Sends the rebuild. The dialog never reaches the command itself: what it owns is the
     confirmation, and the screen decides what to do with it. */
  onConfirm: () => void;
  open: boolean;
  pending: boolean;
}

/* §14 `build_from_analysis` discards the document's content and every stamp, and nothing
   regenerates manual wording. That is the only reason this is a dialog: the press has to
   say what it loses before it loses it. Not dismissible for the same reason - Escape must
   not stand for either answer. */
export const BuildFromAnalysisDialog = ({
  commandsBlocked,
  onClose,
  onConfirm,
  open,
  pending,
}: BuildFromAnalysisDialogProps) => (
  <ConfirmDialog
    confirmDisabled={commandsBlocked}
    confirmLabel="בנייה מחדש מהניתוח החדש"
    dismissible={false}
    headingId="build-from-analysis-heading"
    icon={<RefreshCw aria-hidden="true" />}
    onCancel={onClose}
    onConfirm={onConfirm}
    open={open}
    pending={pending}
    pendingLabel="בונה מחדש…"
    title="בניית המסמך מחדש מהניתוח החדש"
  >
    <div className="flex flex-col gap-3">
      {/* On a phone what the rebuild loses is set apart on a muted ground, the one block
          of the sheet to read before either button. */}
      <p className="max-lg:rounded-control max-lg:bg-cv-surface-muted max-lg:p-3 max-lg:text-support max-lg:leading-6">
        המסמך יעבור לניתוח החדש, וטיוטה חדשה תיווצר ממנו. תוכן הטיוטה הנוכחית יימחק, וכל אישור או קובץ שהופק ממנה לא
        יחולו עוד.
      </p>
      <p className="text-support leading-6 text-cv-text-muted">
        הגשות שכבר נרשמו אינן משתנות: הן שומרות את התוכן והקבצים שנשלחו בפועל.
      </p>
    </div>
  </ConfirmDialog>
);
