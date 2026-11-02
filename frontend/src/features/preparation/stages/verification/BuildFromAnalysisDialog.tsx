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
    /* The design stacks the two answers full-width on a phone: the rebuild over the way out. */
    footerLayout="stack"
    headingId="build-from-analysis-heading"
    icon={<RefreshCw aria-hidden="true" />}
    onCancel={onClose}
    onConfirm={onConfirm}
    open={open}
    pending={pending}
    pendingLabel="בונה מחדש…"
    title="בניית המסמך מחדש מהניתוח החדש"
  >
    {/* What the rebuild loses is set apart on a muted ground, the one block of the dialog
        to read before either button. */}
    <p className="rounded-control bg-cv-surface-muted p-3 text-support leading-6">
      בנייה מחדש מעבירה את המסמך לניתוח החדש ומוחקת את תוכן הטיוטה הנוכחית.
    </p>
  </ConfirmDialog>
);
