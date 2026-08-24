import { type ReactNode, useEffect, useRef } from "react";

interface DialogProps {
  children: ReactNode;
  /* A.5: Escape cancels only when cancelling cannot approve, discard, or overwrite
     content. A conflict or approval dialog passes false and offers explicit choices. */
  dismissible?: boolean;
  footer?: ReactNode;
  headingId: string;
  onClose: () => void;
  open: boolean;
  title: ReactNode;
}

/* Native <dialog> owns the focus trap, the inert background, and focus restoration to
   the invoker, so no dialog dependency is warranted here. Focus is moved to the dialog
   heading on open, as A.5 requires. */
export const Dialog = ({
  children,
  dismissible = true,
  footer,
  headingId,
  onClose,
  open,
  title,
}: DialogProps) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog === null) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
      headingRef.current?.focus();
      return;
    }

    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      aria-labelledby={headingId}
      className="max-w-xl rounded-surface border border-cv-border bg-cv-surface p-0 text-cv-text shadow-overlay"
      onCancel={(event) => {
        if (!dismissible) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="flex flex-col gap-4 p-6" dir="rtl">
        <h2
          className="text-heading-md font-semibold tracking-tight"
          id={headingId}
          ref={headingRef}
          tabIndex={-1}
        >
          {title}
        </h2>
        <div className="text-body leading-7">{children}</div>
        {footer === undefined ? null : (
          <div className="flex flex-wrap justify-end gap-3 border-t border-cv-border pt-4">
            {footer}
          </div>
        )}
      </div>
    </dialog>
  );
};
