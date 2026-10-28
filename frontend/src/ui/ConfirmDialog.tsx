import type { ReactNode } from "react";

import { Button, type ButtonVariant } from "./Button";
import { cx } from "./cx";
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
  /* The question's subject as an icon, shown in a tile over the title on a phone. A
     destructive question draws its tile filled, so the one that cannot be undone does not
     look like the one that can. */
  icon?: ReactNode;
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
   takes. A dialog that collects input is a form dialog and stays on `Dialog` itself.

   On a phone it is the one dialog that does not become a bottom sheet: an interruption
   with two answers stays a centred card, its answers side by side across its width. */
export const ConfirmDialog = ({
  children,
  confirmDisabled = false,
  confirmLabel,
  confirmVariant = "primary",
  dismissible,
  headingId,
  icon,
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
    icon={
      icon === undefined ? undefined : (
        <span
          className={cx(
            "flex size-12 items-center justify-center rounded-surface [&_svg]:size-icon-lg",
            confirmVariant === "destructive" ? "bg-cv-accent text-cv-on-accent" : "bg-cv-surface-muted text-cv-text",
          )}
        >
          {icon}
        </span>
      )
    }
    onClose={onCancel}
    open={open}
    presentation="alert"
    title={title}
  >
    {children}
  </Dialog>
);
