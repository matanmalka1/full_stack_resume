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
    onCancel={onClose}
    onConfirm={onConfirm}
    open={open}
    pending={pending}
    pendingLabel="בונה מחדש…"
    title="בניית המסמך מחדש מהניתוח החדש"
  >
    <div className="flex flex-col gap-3">
      <p>
        המסמך יעבור לניתוח החדש עם בחירת העובדות שהמנוע מציע לו. תוכן הטיוטה הנוכחית יימחק, וכל אישור או קובץ שהופק ממנה
        לא יחולו עוד.
      </p>
      <p className="text-support leading-6 text-cv-text-muted">
        הגשות שכבר נרשמו אינן משתנות: הן שומרות את התוכן והקבצים שנשלחו בפועל.
      </p>
    </div>
  </ConfirmDialog>
);
