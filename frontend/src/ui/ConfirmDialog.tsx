import type { ReactNode } from "react";

import { Button, type ButtonVariant } from "./Button";
import { Dialog } from "./Dialog";

interface ConfirmDialogProps {
  children: ReactNode;
  /* Disables the confirmation without closing the dialog - the command is blocked
     elsewhere on the screen for a reason the dialog does not own. */
  confirmDisabled?: boolean;
  confirmLabel: ReactNode;
  confirmVariant?: Extract<ButtonVariant, "primary" | "destructive">;
  /* Passed through to `Dialog`: false where Escape must not stand for either answer. */
  dismissible?: boolean;
  headingId: string;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  pending: boolean;
  pendingLabel: ReactNode;
  title: ReactNode;
}

/* A question with exactly two answers: go back, or do the one thing the title names. The
   dialog never sends the command - the screen that opened it does, from `onConfirm` - so
   what the caller owns is the copy, and what this owns is the shape every such question
   takes. A dialog that collects input is a form dialog and stays on `Dialog` itself. */
export const ConfirmDialog = ({
  children,
  confirmDisabled = false,
  confirmLabel,
  confirmVariant = "primary",
  dismissible,
  headingId,
  onCancel,
  onConfirm,
  open,
  pending,
  pendingLabel,
  title,
}: ConfirmDialogProps) => (
  <Dialog
    dismissible={dismissible}
    footer={
      <>
        <Button onClick={onCancel} variant="secondary">
          ביטול
        </Button>
        <Button
          disabled={confirmDisabled}
          onClick={onConfirm}
          pending={pending}
          pendingLabel={pendingLabel}
          variant={confirmVariant}
        >
          {confirmLabel}
        </Button>
      </>
    }
    headingId={headingId}
    onClose={onCancel}
    open={open}
    title={title}
  >
    {children}
  </Dialog>
);
