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
export const Dialog = ({ children, dismissible = true, footer, headingId, onClose, open, title }: DialogProps) => {
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
      className="w-full max-w-xl rounded-surface border border-cv-border bg-cv-surface p-0 text-cv-text shadow-overlay backdrop:transition-opacity"
      onCancel={(event) => {
        if (!dismissible) {
          event.preventDefault();
        }
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <div dir="rtl">
        <div className="flex items-start justify-between gap-4 border-b border-cv-border px-6 py-5">
          <h2
            className="text-heading-md font-semibold tracking-tight text-cv-text"
            id={headingId}
            ref={headingRef}
            tabIndex={-1}
          >
            {title}
          </h2>
          {dismissible ? (
            <button
              aria-label="סגירה"
              className="-me-2 -mt-1 inline-flex size-8 shrink-0 items-center justify-center rounded-control text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
              onClick={onClose}
              type="button"
            >
              <svg aria-hidden="true" className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" strokeWidth={1.75} />
              </svg>
            </button>
          ) : null}
        </div>
        <div className="px-6 py-5 text-body leading-7">{children}</div>
        {footer === undefined ? null : (
          <div className="flex flex-wrap justify-end gap-3 border-t border-cv-border px-6 py-4">{footer}</div>
        )}
      </div>
    </dialog>
  );
};
